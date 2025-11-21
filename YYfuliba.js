// fuliba.js  ——  完整信息提取版（今日排名 + 用户名 + 连签 + 累计 + 总排名）
const axios = require('axios');

const cookies = (process.env.FULI_COOKIE || '').split('@').filter(Boolean);
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN;
const TG_CHAT_ID   = process.env.TG_CHAT_ID;

const DOMAINS = [
  "https://www.wnflb2025.com",
  "https://www.wnflb2024.com",
  "https://www.wnflb2023.com",
  "https://www.wnflb99.com",
  "https://www.wnflb.com",
  "https://fuliba2025.bar"
];

async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return console.log("TG 配置缺失");
  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_CHAT_ID,
      text: `<b>${title}</b>\n\n${content}`.slice(0,4090),
      parse_mode: "HTML",
      disable_web_page_preview: true
    }, { timeout: 10000 });
    console.log("Telegram 推送成功 🎉");
  } catch (e) {
    console.log("Telegram 推送失败:", e.response?.data || e.message);
  }
}

async function signOne(cookie, index) {
  for (const base of DOMAINS) {
    try {
      const http = axios.create({
        baseURL: base,
        timeout: 15000,
        headers: {
          'Cookie': cookie.trim(),
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': base + '/'
        }
      });

      // 先访问签到列表页
      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');

      // 提取 formhash
      const formhash = (html.match(/name="formhash" value="(\w{8})"/) || [])[1]
                    || (html.match(/formhash=(\w{8})/) || [])[1];
      if (!formhash) throw 'Cookie失效或formhash获取失败';

      // 提取所有信息（签到前就能拿到）
      const todayRank   = (html.match(/今天第\D*(\d+)\D*名/) || [])[1] || '未知';
      const username    = (html.match(/<span id="username">([^<]+)</) 
                       || html.match(/class="xw1">([^<]+)</) 
                       || [])[1]?.trim() || '未知用户';
      const contiDays   = (html.match(/已连续签到\D*(\d+)/) || [])[1] || '0';
      const totalDays   = (html.match(/累计签到\D*(\d+)/) || [])[1] || '0';
      const totalRank   = (html.match(/个人排名\D*(\d+)/) || html.match(/排名\D*(\d+)/) || [])[1] || '未知';

      // 执行签到
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // 签到后再次确认（防止已签到的情况）
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));
      const newConti = (html.match(/已连续签到\D*(\d+)/) || [])[1] || contiDays;

      const msg = `✅ 签到成功！\n` +
                  `🏆 今日排名：第 <b>${todayRank}</b> 名\n` +
                  `🔥 连签：<b>${newConti}</b> 天（+1）\n` +
                  `📊 累计签到：<b>${totalDays}</b> 天\n` +
                  `🏅 个人总排名：<b>${totalRank}</b> 名\n` +
                  `🌐 域名：${base}`;

      console.log(msg);
      return msg;

    } catch (e) {
      if (base === DOMAINS[DOMAINS.length-1]) {
        return `账号${index}\n❌ 全部域名失效：${e.message || e}`;
      }
    }
  }
}

(async () => {
  if (cookies.length === 0) {
    await sendTG('福利吧签到失败', '未检测到 FULI_COOKIE');
    process.exit(1);
  }

  const results = [];
  for (let i = 0; i < cookies.length; i++) {
    results.push(await signOne(cookies[i], i+1));
    if (i < cookies.length-1) await new Promise(r => setTimeout(r, 3000 + Math.random()*4000));
  }

  const summary = results.join('\n\n');
  console.log('\n' + '='.repeat(50) + '\n' + summary);
  await sendTG(`🔔 福利吧签到报告（${new Date().toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}）`, summary);
})();
