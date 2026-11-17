// e2e_harness.js —— 本地端到端验证 fuliba.js（不依赖 npm 安装 axios）
// 做法：拦截 require('axios')，用 Node 内置 https/http 提供最小兼容实现，
// 然后真正跑一遍 fuliba.js 的完整流程，检查判据与退出码。
const Module = require('module');
const https = require('https');
const http = require('http');
const zlib = require('zlib');
const { URL } = require('url');

function rawRequest(method, urlStr, body, headers, timeout) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const lib = u.protocol === 'https:' ? https : http;
    const req = lib.request(
      {
        method,
        hostname: u.hostname,
        port: u.port || undefined,
        path: u.pathname + u.search,
        headers: { 'Accept-Encoding': 'gzip, deflate', ...headers },
        timeout,
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          let buf = Buffer.concat(chunks);
          const enc = (res.headers['content-encoding'] || '').toLowerCase();
          try {
            if (enc === 'gzip') buf = zlib.gunzipSync(buf);
            else if (enc === 'deflate') buf = zlib.inflateSync(buf);
            else if (enc === 'br') buf = zlib.brotliDecompressSync(buf);
          } catch (_) {
            /* 保持原始字节 */
          }
          // 与 axios 默认行为一致：string 响应按 utf-8 解码
          resolve({ status: res.statusCode, headers: res.headers, data: buf.toString('utf8') });
        });
      }
    );
    req.on('timeout', () => req.destroy(new Error('timeout of ' + timeout + 'ms exceeded')));
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

function makeInstance(defaults = {}) {
  const base = defaults.baseURL || '';
  const headers = defaults.headers || {};
  const timeout = defaults.timeout || 0;
  const validate = defaults.validateStatus || ((s) => s >= 200 && s < 300);
  const join = (p) => (p.startsWith('http') ? p : base.replace(/\/$/, '') + p);

  const doReq = async (method, url, data, opt = {}) => {
    const full = join(url);
    const h = { ...headers, ...(opt.headers || {}) };
    const payload = data === undefined ? undefined : typeof data === 'string' ? data : JSON.stringify(data);
    if (payload && !h['Content-Type']) h['Content-Type'] = 'application/json';
    const res = await rawRequest(method, full, payload, h, opt.timeout || timeout);
    if (!validate(res.status)) {
      const err = new Error(`Request failed with status code ${res.status}`);
      err.response = res;
      err.isAxiosError = true;
      throw err;
    }
    return res;
  };

  return {
    defaults,
    get: (url, opt) => doReq('GET', url, undefined, opt),
    post: (url, data, opt) => doReq('POST', url, data, opt),
    request: (cfg) => doReq(cfg.method || 'GET', cfg.url, cfg.data, cfg),
  };
}

const axiosStub = {
  create: (d) => makeInstance(d),
  get: (url, opt) => makeInstance().get(url, opt),
  post: (url, data, opt) => makeInstance().post(url, data, opt),
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'axios') return axiosStub;
  return origLoad.call(this, request, parent, isMain);
};

module.exports = { axiosStub, makeInstance, rawRequest };
