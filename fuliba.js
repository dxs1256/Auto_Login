// fuliba.js —— 严格判据版（签到结果必须由接口/页面证据确认，绝不默认成功）
const axios = require('axios');

const cookies = (process.env.FULI_COOKIE || '')
  .split('@')
  .map((s) => s.trim())
  .filter(Boolean);

// Telegram 配置
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN;
const TG_CHAT_ID = process.env.TG_CHAT_ID;

// PushPlus 配置 (http://www.pushplus.plus/)
const PUSHPLUS_TOKEN = process.env.PUSHPLUS_TOKEN || '';

// 域名池。已剔除 2026-11 实测死亡的域名：
//   www.wnflb2025.com / fuliba2025.bar -> DNS 解析失败
//   www.wnflb2024.com -> TLS 握手失败
// 可用域名（2026-11-17 实测 200）：wnflb2023.com / wnflb99.com / wnflb00.com / fuliba2023.net
// 可用 FULI_DOMAINS（逗号分隔）整体覆盖，便于本地/自建站测试。
const DOMAINS = process.env.FULI_DOMAINS
  ? process.env.FULI_DOMAINS.split(',').map((s) => s.trim()).filter(Boolean)
  : [
      'https://www.wnflb2023.com',
      'https://www.wnflb99.com',
      'https://www.wnflb00.com',
      'https://fuliba2023.net',
    ];

const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

// 签到接口/页面文案判据
const RE_NOLOGIN = /尚未登录|需要先登录|请先登录|登录后才能|请登录后|请登录再/;
const RE_ALREADY = /已经签到|已签到|签过了|签到过了|重复签到/;
const RE_SUCCESS = /签到成功|签到完成|恭喜签到|签到获得|奖励/;

class AuthError extends Error {}

// Telegram 推送
async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return console.log('TG 配置缺失，跳过 TG 推送');
  try {
    await axios.post(
      `https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`,
      {
        chat_id: TG_CHAT_ID,
        text: `<b>${title}</b>\n\n${content}`.slice(0, 4090),
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      },
      { timeout: 10000 }
    );
    console.log('Telegram 推送成功 🎉');
  } catch (e) {
    console.log('Telegram 推送失败:', e.response?.data || e.message);
  }
}

// PushPlus 推送
async function sendPushPlus(title, content) {
  if (!PUSHPLUS_TOKEN) return console.log('PushPlus Token 缺失，跳过推送');
  try {
    await axios.post(
      'http://www.pushplus.plus/send',
      {
        token: PUSHPLUS_TOKEN,
        title: title,
        content: content.replace(/\n/g, '<br>'),
        template: 'html',
      },
      { timeout: 10000 }
    );
    console.log('PushPlus 推送成功 🎉');
  } catch (e) {
    console.log('PushPlus 推送失败:', e.response?.data || e.message);
  }
}

// 去掉 script/style/注释/花括号模板占位。
// 关键：签到页里含有 {constant}/{days}/{todayrank} 等 JS 模板和 #ff8800 这类色值，
// 不清理就会被正则跨段匹配成"连签 8800 天""总排名 2"这种假数据。
function stripNoise(html) {
  return String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/\{[^{}]*\}/g, ' ');
}

// 登录态判定：Discuz 页面里 window.CHATROOM_CONFIG 带 "uid":<数字>，游客为 0。
function sessionOf(html) {
  const raw = String(html || '');
  const uidMatch = raw.match(/"uid"\s*:\s*(\d+)/);
  const uid = uidMatch ? Number(uidMatch[1]) : null;
  const hasUserNode = /id="myusername"|class="xw1"/.test(raw);
  const guestBlock = RE_NOLOGIN.test(stripNoise(raw));
  const loggedIn = uid !== null ? uid > 0 : hasUserNode && !guestBlock;
  return { uid, hasUserNode, guestBlock, loggedIn };
}

// 把 inajax 的 XML/CDATA 响应压成纯文本。
// 注意：Discuz 会把内联脚本直接拼在文案后面（errorhandle_/fx_chk_menu/$('...')），
// 只去 HTML 标签会把这些 JS 一起带进通知正文，所以先整体剔除 <script>/<style> 的内容。
function ajaxText(body) {
  const raw = String(body || '');
  const cdata = (raw.match(/<!\[CDATA\[([\s\S]*?)\]\]>/) || [])[1] || raw;
  const strip = (s) =>
    s
      .replace(/&nbsp;/g, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

  const noScript = strip(
    cdata
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<!--[\s\S]*?-->/g, ' ')
  );
  // 极少数站点把整段文案塞在 <script> 里，此时退回"只去标签"的版本，避免把内容清空
  return noScript || strip(cdata);
}

// 把回执提炼成给人看的一句话：截断 JS 尾巴、去掉 Discuz 弹层装饰前缀、限长。
function cleanNote(text, max = 120) {
  let t = String(text || '').replace(/\s+/g, ' ').trim();
  if (!t) return '';
  // 内联 JS 的起点：从第一个 JS 标记处直接截断
  const cut = t.search(/if\s*\(\s*typeof|function\s*\(|\$\s*\(|\bvar\s+\w+\s*=|errorhandle/i);
  if (cut > 0) t = t.slice(0, cut);
  // 去掉弹层装饰：Discuz 的"提示信息 / 关闭"
  t = t.replace(/^(提示信息|信息提示|提示)\s*(关闭)?\s*/i, '').trim();
  t = t.replace(/\s+/g, ' ').trim();
  return t.length > max ? t.slice(0, max) + '…' : t;
}

// 签到结果判定：先排除未登录，再判重复，最后才认成功。
function judgeCheckin(text, httpStatus) {
  const t = String(text || '');
  if (!t) return { state: 'unknown', note: `接口无正文（HTTP ${httpStatus}）` };
  if (RE_NOLOGIN.test(t)) return { state: 'nologin', note: cleanNote(t) };
  if (RE_ALREADY.test(t)) return { state: 'already', note: cleanNote(t) };
  if (RE_SUCCESS.test(t)) return { state: 'success', note: cleanNote(t) };
  return { state: 'unknown', note: cleanNote(t) };
}

// 只认明确数字，且数字距关键词不超过 24 个非数字字符，避免跨段误匹配。
function readStats(html) {
  const t = stripNoise(html);
  const pick = (...pats) => {
    for (const p of pats) {
      const m = t.match(p);
      if (m && m[1] && Number.isFinite(Number(m[1]))) return m[1];
    }
    return null;
  };
  return {
    todayRank: pick(
      /您今天第[^\d]{0,24}(\d+)/,
      /今天第[^\d]{0,12}(\d+)/,
      /今日第[^\d]{0,24}(\d+)/,
      /今日签到排名[^\d]{0,24}(\d+)/,
      /第[^\d]{0,12}(\d+)[^\d]{0,12}名签到/
    ),
    contiDays: pick(/已连续签到[^\d]{0,24}(\d+)/, /连续签到[^\d]{0,24}(\d+)/, /连签[^\d]{0,12}(\d+)/),
    totalDays: pick(/累计签到[^\d]{0,24}(\d+)/, /总签到[^\d]{0,24}(\d+)/, /签到总数[^\d]{0,16}(\d+)/),
    totalRank: pick(/个人排名[^\d]{0,24}(\d+)/, /总排名[^\d]{0,24}(\d+)/),
  };
}

function fmt(stat, unit) {
  return stat === null ? '未获取' : `${stat} ${unit}`;
}

function formatStats(stats) {
  return [
    `🏆 今日排名：第 ${fmt(stats.todayRank, '名')}`,
    `🔥 连签天数：${fmt(stats.contiDays, '天')}`,
    `📊 累计签到：${fmt(stats.totalDays, '天')}`,
    `🏅 个人总排名：${fmt(stats.totalRank, '名')}`,
  ].join('\n');
}

async function signOne(cookie, index) {
  const tag = `账号${index}`;
  let lastErr = null;
  let authFailures = 0;

  for (const base of DOMAINS) {
    try {
      const http = axios.create({
        baseURL: base,
        timeout: 20000,
        maxRedirects: 5,
        headers: {
          Cookie: cookie,
          'User-Agent': UA,
          Referer: base + '/',
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'zh-CN,zh;q=0.9',
        },
        validateStatus: (s) => s >= 200 && s < 500,
      });

      // 1) 打开签到页，先确认登录态
      const before = await http.get('/plugin.php?id=fx_checkin:list');
      const beforeHtml = before.data;
      const sess = sessionOf(beforeHtml);
      if (!sess.loggedIn) {
        authFailures += 1;
        throw new AuthError(`站点返回未登录页面（uid=${sess.uid ?? '未知'}），Cookie 已失效`);
      }

      const formhash =
        (String(beforeHtml).match(/name="formhash"\s+value="([0-9a-zA-Z]{8})"/) || [])[1] ||
        (String(beforeHtml).match(/FX_FORMHASH\s*=\s*"([0-9a-zA-Z]{8})"/) || [])[1] ||
        (String(beforeHtml).match(/formhash=([0-9a-zA-Z]{8})/) || [])[1];
      if (!formhash) throw new Error('已登录但未能提取 formhash，页面结构可能已改版');

      // 2) 调用签到接口，并解析真实返回
      const resp = await http.get(
        `/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`
      );
      const respText = ajaxText(resp.data);
      const verdict = judgeCheckin(respText, resp.status);

      // 3) 回查页面拿真实数据
      const after = await http.get('/plugin.php?id=fx_checkin:list');
      const stats = readStats(after.data);
      const statsBlock = formatStats(stats);

      if (verdict.state === 'nologin') {
        authFailures += 1;
        throw new AuthError(`签到接口返回未登录：${verdict.note}`);
      }

      if (verdict.state === 'already') {
        const msg = `${tag}\nℹ️ 今日已签到（未重复签到）\n${statsBlock}\n💬 站点反馈：${verdict.note}\n🌐 站点：${base}`;
        console.log(msg);
        return { ok: true, msg };
      }

      if (verdict.state === 'success') {
        const msg = `${tag}\n✅ 签到成功（接口已确认）\n${statsBlock}\n💬 站点反馈：${verdict.note}\n🌐 站点：${base}`;
        console.log(msg);
        return { ok: true, msg };
      }

      // 接口没给明确语义：只有在页面数据可读（说明确实处于登录态）时才允许"待确认"，绝不自动算成功
      const pageReadable = stats.contiDays !== null || stats.totalDays !== null;
      const msg =
        `${tag}\n⚠️ 签到结果未确认\n` +
        `${statsBlock}\n` +
        `💬 接口返回：${verdict.note}\n` +
        `🌐 站点：${base}\n` +
        (pageReadable
          ? '📌 页面数据可读，但接口未返回成功语义，请登录站点人工确认今日签到状态'
          : '📌 页面数据也不可读，无法判断签到是否生效');
      console.log(msg);
      return { ok: false, msg };
    } catch (e) {
      lastErr = e;
      if (e instanceof AuthError) {
        // Cookie 对所有域名都失效，没必要继续遍历
        if (authFailures >= 2) break;
        continue;
      }
      continue;
    }
  }

  const reason =
    authFailures > 0
      ? `Cookie 已失效或登录态丢失，请重新获取 FULI_COOKIE（${lastErr?.message || ''}）`
      : `全部域名均不可用：${lastErr?.message || '未知错误'}`;
  const msg = `${tag}\n❌ 签到失败\n💬 原因：${reason}`;
  console.log(msg);
  return { ok: false, msg };
}

async function main() {
  if (cookies.length === 0) {
    const errMsg = '未检测到 FULI_COOKIE 环境变量';
    console.log(errMsg);
    await Promise.all([sendTG('福利吧签到失败', errMsg), sendPushPlus('福利吧签到失败', errMsg)]);
    process.exit(1);
  }

  const results = [];
  let allOk = true;
  for (let i = 0; i < cookies.length; i++) {
    const { ok, msg } = await signOne(cookies[i], i + 1);
    if (!ok) allOk = false;
    results.push(msg);
    if (i < cookies.length - 1) {
      await new Promise((r) => setTimeout(r, 3000 + Math.random() * 4000));
    }
  }

  const summary = results.join('\n\n');
  console.log('\n' + '='.repeat(60) + '\n签到完成\n' + '='.repeat(60) + '\n' + summary + '\n' + '='.repeat(60));

  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  const title = `${allOk ? '🔔' : '⚠️'} 福利吧签到报告（${now}）`;

  await Promise.all([sendTG(title, summary), sendPushPlus(title, summary)]);

  // 失败必须让 Actions 变红，否则"绿色成功"会继续掩盖问题
  if (!allOk) process.exitCode = 1;
}

// 导出纯函数给自测用；被 require 时不自启，直接执行时自启
module.exports = {
  signOne,
  readStats,
  sessionOf,
  judgeCheckin,
  ajaxText,
  cleanNote,
  stripNoise,
  DOMAINS,
};

if (require.main === module) {
  main();
}
