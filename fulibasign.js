// fulibasign.js  ——  GitHub Actions 专用自带 Telegram 通知版
const axios = require('axios');

// ================== 配置区（从 GitHub Secrets 读取）==================
const cookies = (process.env.FULI_COOKIE || '').split('@').filter(Boolean);
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN;
const TG_CHAT_ID   = process.env.TG_CHAT_ID;   // 支持私聊ID或群组ID（负数）

const DOMAINS = [
  "https://www.wnflb2025.com",
  "https://www.wnflb2024.com",
  "https://www.wnflb2023.com",
  "https://www.wnflb99.com",
  "https://www.wnflb.com",
  "https://fuliba2025.bar",
  "https://fuliba2024.net"
];

// ================== Telegram 推送函数 ==================
async function sendTG(title, content = '') {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) {
    console.log("⚠️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过推送");
    return;
  }
  const text = `<b>${title}</b>\n\n${content}`.slice(0, 4090);
  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_CHAT_ID,
      text,
      parse_mode: "HTML",
      disable_web_page_preview: true
    }, { timeout: 10000 });
    console.log("Telegram 推送成功 🎉");
  } catch (e) {
    console.log("Telegram 推送失败:", e.response?.data || e.message);
  }
}

// ================== 单账号签到函数 ==================
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

      // 1. 取 formhash
      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');
      const formhash = (html.match(/name="formhash" value="(\w{8})"/) || [])[1]
                    || (html.match(/formhash=(\w{8})/) || [])[1];
      if (!formhash) throw 'formhash 获取失败（Cookie可能过期）';

      // 2. 签到
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // 3. 验证结果
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));
      const conti = (html.match(/已连续签到\D*(\d+)/) || [])[1] || '？';
      const total = (html.match(/累计签到\D*(\d+)/) || [])[1] || '？';

      const msg = `账号${index}\n✅ 签到成功！\n连续 <b>${conti}</b> 天\n累计 <b>${total}</b> 天\n域名：${base}`;
      console.log(msg);
      return msg;
    } catch (e) {
      const err = e.message || e;
      console.log(`[${base}] 失败：${err}`);
      if (base === DOMAINS[DOMAINS.length - 1]) {
        const msg = `账号${index}\n❌ 全部域名失效：${err}`;
        console.log(msg);
        return msg;
      }
    }
  }
}

// ================== 主函数 ==================
(async () => {
  console.log(`开始执行福利吧签到，共 ${cookies.length} 个账号\n`);

  if (cookies.length === 0) {
    const warn = '❌ 未检测到 FULI_COOKIE 环境变量！';
    console.log(warn);
    await sendTG('福利吧签到失败', warn);
    process.exit(1);
  }

  const results = [];
  for (let i = 0; i < cookies.length; i++) {
    results.push(await signOne(cookies[i], i + 1));
    // 防风控随机延迟
    if (i < cookies.length - 1) await new Promise(r => setTimeout(r, 3000 + Math.random() * 4000));
  }

  const summary = results.join('\n\n');
  console.log('\n' + '='.repeat(50) + '\n最终结果：\n' + summary);

  // 统一发送 Telegram 通知
  await sendTG('🔔 福利吧签到报告', summary);
})();
