const axios = require('axios');
const { sendNotify } = require('./sendNotify.js');

const cookies = (process.env.FULI_COOKIE || '').split('@').filter(Boolean);
const DOMAINS = [
  "https://www.wnflb2025.com",
  "https://www.wnflb2024.com",
  "https://www.wnflb99.com",
  "https://www.wnflb.com",
  "https://fuliba2025.bar",
  "https://fuliba2024.net"
];

async function sign(cookie) {
  for (const base of DOMAINS) {
    try {
      const http = axios.create({
        baseURL: base,
        timeout: 15000,
        headers: {
          'Cookie': cookie,
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': base
        }
      });

      // 拿 formhash
      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');
      const formhash = html.match(/name="formhash"\s+value="(\w{8})"/)?.[1]
                    || html.match(/formhash=(\w{8})/)?.[1];
      if (!formhash) throw 'formhash 获取失败';

      // 签到
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // 验证结果
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));
      const conti = html.match(/已连续签到\D*(\d+)/)?.[1] || '?';
      const total = html.match(/累计签到\D*(\d+)/)?.[1] || '?';

      const msg = `✅ 签到成功！\n连续 ${conti} 天\n累计 ${total} 天\n使用域名：${base}`;
      console.log(msg);
      return msg;
    } catch (e) {
      const err = e.message || e;
      console.log(`${base} 失败：${err}`);
      if (base === DOMAINS[DOMAINS.length-1]) return `❌ 全挂了：${err}`;
    }
  }
}

(async () => {
  if (!cookies.length) return console.log('未配置 FULI_COOKIE');

  const results = [];
  for (let i = 0; i < cookies.length; i++) {
    console.log(`\n=== 账号 ${i+1} ===`);
    results.push(await sign(cookies[i]));
    await new Promise(r => setTimeout(r, 3000 + Math.random()*4000));
  }

  const summary = results.join('\n\n');
  console.log('\n' + '='.repeat(40) + '\n' + summary);

  await sendNotify('福利吧签到报告', summary);
})();
