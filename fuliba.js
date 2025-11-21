// fuliba.js —— 完整信息提取版（支持已签到/未签到，全部域名稳定）
const axios = require('axios');

const cookies = (process.env.FULI_COOKIE || '').split('@').filter(Boolean);
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN;
const TG_CHAT_ID = process.env.TG_CHAT_ID;

const DOMAINS = [
  "https://www.wnflb2025.com",
  "https://www.wnflb2024.com",
  "https://www.wnflb2023.com",
  "https://www.wnflb99.com",
  "https://www.wnflb00.com",
  "https://fuliba2025.bar"
];

async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return console.log("TG 配置缺失");
  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_CHAT_ID,
      text: `<b>${title}</b>\n\n${content}`.slice(0, 4090),
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
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
          'Referer': base + '/',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
      });

      // 第一次访问签到页面
      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');

      // 提取 formhash
      const formhash = (html.match(/name="formhash" value="(\w{8})"/) || [])[1]
                    || (html.match(/formhash=(\w{8})/) || [])[1];
      if (!formhash) throw new Error('Cookie失效或formhash获取失败');

      // 增强版信息提取（兼容已签到和未签到）
      const getInfo = (text) => ({
        username: (text.match(/id="username">([^<]+)</) 
                || text.match(/class="xw1">([^<]+)</) 
                || text.match(/<em id="myusername">([^<]+)</) 
                || [])[1]?.trim() || '未知用户',

        todayRank: (text.match(/今日签到排名\D*(\d+)/) 
                || text.match(/已签到\D*第\D*(\d+)\D*名/) 
                || text.match(/第\D*(\d+)\D*名签到/) 
                || text.match(/今日第\D*(\d+)/) 
                || [])[1] || '未知',

        contiDays: (text.match(/已连续签到\D*(\d+)/) 
                || text.match(/连续签到\D*(\d+)/) 
                || text.match(/连签\D*(\d+)/) 
                || [])[1] || '0',

        totalDays: (text.match(/累计签到\D*(\d+)/) 
                || text.match(/总签到\D*(\d+)/) 
                || text.match(/签到总数\D*(\d+)/) 
                || text.match(/累计\D*(\d+)\D*天/) 
                || [])[1] || '0',

        totalRank: (text.match(/个人排名\D*(\d+)/) 
                || text.match(/总排名\D*(\d+)/) 
                || text.match(/排名\D*(\d+)/) 
                || text.match(/第\D*(\d+)\D*名/) 
                || [])[1] || '未知'
      });

      const before = getInfo(html);

      // 执行签到（已签到时也会返回成功，不会报错）
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // 签到后重新抓取页面，确保数据最新
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));
      const after = getInfo(html);

      // 以签到后的数据为准，防止漏掉+1
      const msg = `✅ 签到成功\n` +
                  `🏆 今日排名：第 <b>${after.todayRank}</b> 名\n` +
                  `🔥 连签天数：<b>${after.contiDays}</b> 天\n` +
                  `📊 累计签到：<b>${after.totalDays}</b> 天\n` +
                  `🏅 个人总排名：<b>${after.totalRank}</b> 名\n` +
                  `🌐 站点：${base}`;

      console.log(msg);
      return msg;

    } catch (e) {
      // 只在最后一个域名失败时才报错
      if (base === DOMAINS[DOMAINS.length - 1]) {
        const errMsg = `账号${index}\n❌ 全部域名失效：${e.message || e}`;
        console.log(errMsg);
        return errMsg;
      }
      // 否则继续尝试下一个域名
      continue;
    }
  }
  return `账号${index}\n❌ 未知错误：所有域名均未返回成功`;
}

(async () => {
  if (cookies.length === 0) {
    await sendTG('福利吧签到失败', '未检测到 FULI_COOKIE 环境变量');
    process.exit(1);
  }

  const results = [];
  for (let i = 0; i < cookies.length; i++) {
    const result = await signOne(cookies[i], i + 1);
    results.push(result);
    // 防反爬，随机延迟 3~7 秒
    if (i < cookies.length - 1) {
      await new Promise(r => setTimeout(r, 3000 + Math.random() * 4000));
    }
  }

  const summary = results.join('\n\n');
  console.log('\n' + '='.repeat(60) + '\n签到完成\n' + '='.repeat(60) + '\n' + summary + '\n' + '='.repeat(60));

  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  await sendTG(`🔔 福利吧签到报告（${now}）`, summary);
})();
