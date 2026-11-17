// verify.js —— 进程内验收：不 spawn 子进程（沙箱禁止管道 stdio），
// 直接 require fuliba.js 的导出函数，配合内置 HTTP mock 跑真实请求路径。
require('./e2e_harness');
const fs = require('fs');
const http = require('http');
const { URL } = require('url');

const lib = require('./fuliba.js');

let pass = 0;
let fail = 0;
const check = (name, actual, expected) => {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  console.log(`${ok ? '✅' : '❌'} ${name}  实际=${JSON.stringify(actual)} 期望=${JSON.stringify(expected)}`);
  ok ? pass++ : fail++;
};

/* ===================== 内置 mock 站点 ===================== */
const PAGES = {
  loggedIn: (conti, days, rank) => `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="um"><strong class="vwmy"><a id="myusername">tester</a></strong></div>
<script>window.CHATROOM_CONFIG={"api":"plugin.php?id=chatroom:api","formhash":"16401a3a","uid":98765,"username":"tester"};</script>
<div id="fx_checkin_menu"><div class="item" id="fx_checkin_menut"><em>签到成功!</em>
<p>您今天第<i>${rank}</i>个签到，签到排名竞争激烈，记得每天都来签到哦！</p></div>
<div class="calendar_foo" id="fx_checkin_menub">已连续签到:<i>${conti}</i>天，累计签到:<i>${days}</i>天</div></div>
<input type="hidden" name="formhash" value="16401a3a" />
<script>var FX_FORMHASH="16401a3a";</script></body></html>`,
  guest: `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<script>window.CHATROOM_CONFIG={"api":"plugin.php?id=chatroom:api","formhash":"0c3743b0","uid":0,"username":"","cansend":0};</script>
<div id="messagetext"><p>抱歉，您尚未登录，无法进行此操作</p></div>
<div id="fx_checkin_menu"><div class="calendar_foo">已连续签到:<i>{constant}</i>天，累计签到:<i>{days}</i>天</div></div>
<style>.can_resign{color:#ff8800}</style>
<input type="hidden" name="formhash" value="0c3743b0" /></body></html>`,
};

const ajax = (inner) => `<?xml version="1.0" encoding="utf-8"?>\r\n<root><![CDATA[\r\n${inner}\r\n]]></root>`;

function startMock(mode, port) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const u = new URL(req.url, `http://127.0.0.1:${port}`);
      const id = u.searchParams.get('id') || '';
      const loggedIn = (req.headers.cookie || '').includes('auth=1');
      if (id === 'fx_checkin:list') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        return res.end(loggedIn ? PAGES.loggedIn(2032, 2032, 1888) : PAGES.guest);
      }
      if (id === 'fx_checkin:checkin') {
        res.writeHead(200, { 'Content-Type': 'text/xml; charset=utf-8' });
        if (!loggedIn) return res.end(ajax('<em>抱歉，您需要先登录才能继续本操作</em>'));
        if (mode === 'already') return res.end(ajax('<p>您今天已经签到过了，请勿重复签到</p>'));
        if (mode === 'opaque') return res.end(ajax('<p>系统维护中</p>'));
        return res.end(ajax('<p>恭喜您，签到成功，获得 3 金币</p>'));
      }
      res.writeHead(404);
      res.end('nf');
    });
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

/* ===================== 验收 ===================== */
(async () => {
  console.log('—— 第一层：纯函数判据（真实线上游客页）——');
  const guest = fs.readFileSync('../axios_like.html', 'utf8');
  check('游客 uid=0', lib.sessionOf(guest).uid, 0);
  check('游客 loggedIn=false', lib.sessionOf(guest).loggedIn, false);
  check('游客页 无假连签(旧版 8800)', lib.readStats(guest).contiDays, null);
  check('游客页 无假累计(旧版 8800)', lib.readStats(guest).totalDays, null);
  check('游客页 无假总排名(旧版 2)', lib.readStats(guest).totalRank, null);

  const loggedIn = guest.replace(/"uid":0/, '"uid":98765').replace('<i>{constant}</i>', '<i>2031</i>').replace('<i>{days}</i>', '<i>2031</i>');
  check('已登录 uid', lib.sessionOf(loggedIn).uid, 98765);
  check('已登录 loggedIn=true', lib.sessionOf(loggedIn).loggedIn, true);
  check('已登录 连签', lib.readStats(loggedIn).contiDays, '2031');

  const wrap = ajax;
  check('语义-成功', lib.judgeCheckin(lib.ajaxText(wrap('<p>恭喜您，签到成功，获得 3 金币</p>')), 200).state, 'success');
  check('语义-已签到', lib.judgeCheckin(lib.ajaxText(wrap('<p>您今天已经签到过了</p>')), 200).state, 'already');
  check('语义-未登录优先于成功', lib.judgeCheckin(lib.ajaxText(wrap('<em>您需要先登录才能继续</em><p>签到成功</p>')), 200).state, 'nologin');
  check('语义-无关文案', lib.judgeCheckin(lib.ajaxText(wrap('<p>系统维护中</p>')), 200).state, 'unknown');

  console.log('\n—— 第二层：真实 HTTP 请求路径（内置 mock，进程内）——');
  const CASES = [
    { name: '登录+签到成功', mode: 'success', cookie: 'auth=1', wantOk: true, wantKeyword: '签到成功（接口已确认）' },
    { name: '登录+今日已签到', mode: 'already', cookie: 'auth=1', wantOk: true, wantKeyword: '今日已签到（未重复签到）' },
    { name: '登录+接口语义不明', mode: 'opaque', cookie: 'auth=1', wantOk: false, wantKeyword: '签到结果未确认' },
    { name: '无登录态', mode: 'success', cookie: 'auth=0', wantOk: false, wantKeyword: 'Cookie 已失效' },
  ];

  const OLD_DOMAINS = lib.DOMAINS.slice();
  let port = 18090;
  for (const c of CASES) {
    port += 1;
    const server = await startMock(c.mode, port);
    const base = `http://127.0.0.1:${port}`;
    lib.DOMAINS.length = 0;
    lib.DOMAINS.push(base);

    const res = await lib.signOne(c.cookie, 1);
    check(`${c.name} → ok=${c.wantOk}`, res.ok, c.wantOk);
    check(`${c.name} → 含"${c.wantKeyword}"`, res.msg.includes(c.wantKeyword), true);
    if (!c.wantOk) {
      check(`${c.name} → 绝不出现"✅ 签到成功"`, res.msg.includes('✅ 签到成功'), false);
    }
    server.close();
  }
  lib.DOMAINS.length = 0;
  OLD_DOMAINS.forEach((d) => lib.DOMAINS.push(d));

  console.log('\n—— 第三层：域名全不可用 ——');
  lib.DOMAINS.length = 0;
  lib.DOMAINS.push('https://nonexistent-a.example.invalid', 'https://nonexistent-b.example.invalid');
  const dead = await lib.signOne('auth=1', 1);
  check('域名全死 → ok=false', dead.ok, false);
  check('域名全死 → 绝不报成功', dead.msg.includes('签到成功'), false);
  check('域名全死 → 给出失败原因', /❌ 签到失败/.test(dead.msg), true);

  console.log('\n—— 第四层：真实线上站点回归（无效 Cookie）——');
  lib.DOMAINS.length = 0;
  lib.DOMAINS.push('https://www.wnflb2023.com');
  const online = await lib.signOne('invalid_cookie=1', 1);
  check('线上无效 Cookie → ok=false', online.ok, false);
  check('线上无效 Cookie → 绝不报成功', online.msg.includes('签到成功'), false);

  console.log(`\n结果: 通过 ${pass} 项，失败 ${fail} 项`);
  process.exit(fail === 0 ? 0 : 1);
})();
