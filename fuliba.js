// fuliba.js —— 强化信息提取版（彻底解决排名获取不到的问题）
const axios = require('axios');

const cookies = (process.env.FULI_COOKIE || '').split('@').filter(Boolean);

// Telegram 配置
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN;
const TG_CHAT_ID = process.env.TG_CHAT_ID;

// PushPlus 配置
const PUSHPLUS_TOKEN = process.env.PUSHPLUS_TOKEN || ''; 

const DOMAINS = [
  "https://www.wnflb2025.com",
  "https://www.wnflb2024.com",
  "https://www.wnflb2023.com",
  "https://www.wnflb99.com",
  "https://www.wnflb00.com",
  "https://fuliba2025.bar"
];

// Telegram 推送
async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return console.log("TG 配置缺失，跳过 TG 推送");
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

// PushPlus 推送
async function sendPushPlus(title, content) {
  if (!PUSHPLUS_TOKEN) return console.log("PushPlus Token 缺失，跳过推送");
  try {
    const htmlContent = content.replace(/\n/g, '<br>');
    await axios.post('http://www.pushplus.plus/send', {
      token: PUSHPLUS_TOKEN,
      title: title,
      content: htmlContent,
      template: 'html'
    }, { timeout: 10000 });
    console.log("PushPlus 推送成功 🎉");
  } catch (e) {
    console.log("PushPlus 推送失败:", e.response?.data || e.message);
  }
}

async function signOne(cookie, index) {
  for (const base of DOMAINS) {
    try {
      const http = axios.create({
        baseURL: base,
        timeout: 10000,
        headers: {
          'Cookie': cookie.trim(),
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Referer': base + '/',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
      });

      // --- 步骤 1: 访问页面获取 formhash ---
      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');

      // 提取 formhash (增加容错)
      const formhash = (html.match(/name="formhash" value="(\w+)"/) || [])[1]
                    || (html.match(/formhash=(\w+)/) || [])[1];
      
      if (!formhash) {
          if (html.includes('请先登录')) throw new Error('Cookie 已失效');
          throw new Error('未能获取到 formhash');
      }

      // --- 步骤 2: 执行签到动作 ---
      // 不管是否已签到，执行一次，防止数据没更新
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // --- 步骤 3: 重新抓取页面，获取最新的排名和天数 ---
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));

      // 增强版信息提取（关键优化：使用 [^\d]* 过滤 HTML 标签干扰）
      const getInfo = (text) => {
        // 先清理一下 HTML 中的换行符，防止正则匹配失效
        const cleanText = text.replace(/\s+/g, ' ');
        
        return {
          username: (cleanText.match(/id="username">([^<]+)</) 
                  || cleanText.match(/class="xw1">([^<]+)</) 
                  || cleanText.match(/"myusername">([^<]+)</) 
                  || [])[1]?.trim() || '未知用户',

          // 解决今日排名获取不到的关键：支持 <span> 标签包裹
          todayRank: (cleanText.match(/今日签到排名[^\d]*(\d+)/) 
                  || cleanText.match(/今日第[^\d]*(\d+)[^\d]*名/) 
                  || cleanText.match(/已签到[^\d]*第[^\d]*(\d+)/) 
                  || cleanText.match(/font_24">(\d+)</)
                  || [])[1] || '待更新',

          contiDays: (cleanText.match(/已连续签到[^\d]*(\d+)/) 
                  || cleanText.match(/连续签到[^\d]*(\d+)/) 
                  || cleanText.match(/连签[^\d]*(\d+)/) 
                  || [])[1] || '0',

          totalDays: (cleanText.match(/累计签到[^\d]*(\d+)/) 
                  || cleanText.match(/总签到[^\d]*(\d+)/) 
                  || cleanText.match(/累计[^\d]*(\d+)[^\d]*天/) 
                  || [])[1] || '0',

          totalRank: (cleanText.match(/个人排名[^\d]*(\d+)/) 
                  || cleanText.match(/总排名[^\d]*(\d+)/) 
                  || cleanText.match(/排名[^\d]*(\d+)/) 
                  || [])[1] || 'N/A'
        };
      };

      const after = getInfo(html);
      
      const msg = `✅ 账号：<b>${after.username}</b>\n` +
                  `🏆 今日排名：第 <b>${after.todayRank}</b> 名\n` +
                  `🔥 连签天数：<b>${after.contiDays}</b> 天\n` +
                  `📊 累计签到：<b>${after.totalDays}</b> 天\n` +
                  `🏅 个人总排名：<b>${after.totalRank}</b> 名\n` +
                  `🌐 站点：${base}`;

      console.log(msg.replace(/<[^>]+>/g, '')); // 终端打印去掉 HTML 标签
      return msg;

    } catch (e) {
      // 如果当前域名失败，尝试下一个
      console.log(`站点 ${base} 尝试失败: ${e.message}`);
      if (base === DOMAINS[DOMAINS.length - 1]) {
        return `账号${index}\n❌ 全部域名访问失败：${e.message}`;
      }
      continue;
    }
  }
}

(async () => {
  if (cookies.length === 0) {
    const errMsg = '未检测到 FULI_COOKIE 环境变量';
    console.log(errMsg);
    await sendTG('福利吧签到失败', errMsg);
    return;
  }

  const results = [];
  for (let i = 0; i < cookies.length; i++) {
    console.log(`\n正在处理第 ${i + 1} 个账号...`);
    const result = await signOne(cookies[i], i + 1);
    results.push(result);
    
    // 账号间隔随机延迟
    if (i < cookies.length - 1) {
      const wait = Math.floor(Math.random() * 4000) + 3000;
      await new Promise(r => setTimeout(r, wait));
    }
  }

  const summary = results.join('\n\n' + '-'.repeat(20) + '\n\n');
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  const title = `🔔 福利吧签到报告（${now}）`;

  await Promise.all([
    sendTG(title, summary),
    sendPushPlus(title, summary)
  ]);
})();
