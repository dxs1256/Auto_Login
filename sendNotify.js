async function tgBotNotify(text, desp) {
  const token = process.env.TG_BOT_TOKEN;
  const chatId = process.env.TG_CHAT_ID || process.env.TG_USER_ID; // 兼容旧变量
  if (!token || !chatId) return;

  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: `${text}\n\n${desp}`.slice(0, 4090),
    parse_mode: "HTML",
    disable_web_page_preview: true
  };

  try {
    const axios = require('axios');
    await axios.post(url, body, { timeout: 10000 });
    console.log("Telegram 推送成功 🎉");
  } catch (e) {
    console.log("Telegram 推送失败:", e.message);
  }
}

async function sendNotify(title, content) {
  await tgBotNotify(title, content);
}

module.exports = { sendNotify };
