/*
 火烧云概率监控脚本 v2.30
 功能：监控日出日落火烧云概率，支持美化版企业微信和Telegram通知
*/

const axios = require('axios');

// ==================== 配置区 ====================
const CITY = process.env.SUNSET_CITY || '广东省-深圳';
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5');
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS'];
const EVENTS = ['set_1', 'set_2', 'rise_1']; // 常用：今天落日、明天落日、明天日出
const TIMEZONE = process.env.TIMEZONE || 'CST'; 

const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;
const QUERY_DELAY = 1000;

const WX_WEBHOOK_URL = process.env.WX_WEBHOOK_URL || '';
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || '';
const TG_CHAT_ID = process.env.TG_CHAT_ID || '';

// ==================== 常量与工具 ====================
const EVENT_NAMES = {
  'set_1': '今天落日 Today Sunset',
  'set_2': '明天落日 Tomorrow Sunset',
  'rise_1': '明天日出 Tomorrow Sunrise',
  'rise_2': '后天日出 Next Day Sunrise'
};

const QUALITY_LEVELS = {
  excellent: { threshold: 0.8, text: '极佳', emoji: '🔥', color: 'warning' },
  good: { threshold: 0.6, text: '很好', emoji: '✨', color: 'warning' },
  normal: { threshold: 0.4, text: '一般', emoji: '☀️', color: 'info' },
  poor: { threshold: 0.2, text: '较差', emoji: '🌤️', color: 'comment' },
  none: { threshold: 0, text: '不烧', emoji: '❌', color: 'comment' }
};

// 生成进度条
function getProgressBar(quality) {
  const total = 10;
  const active = Math.round(quality * total);
  return '█'.repeat(active) + '░'.repeat(total - active);
}

function getQualityInfo(quality) {
  if (quality >= QUALITY_LEVELS.excellent.threshold) return QUALITY_LEVELS.excellent;
  if (quality >= QUALITY_LEVELS.good.threshold) return QUALITY_LEVELS.good;
  if (quality >= QUALITY_LEVELS.normal.threshold) return QUALITY_LEVELS.normal;
  if (quality >= QUALITY_LEVELS.poor.threshold) return QUALITY_LEVELS.poor;
  return QUALITY_LEVELS.none;
}

function getAodInfo(aod) {
  const val = parseFloat(aod);
  if (val < 0.15) return { text: '极纯净', emoji: '💎' };
  if (val < 0.3) return { text: '良好', emoji: '🌿' };
  return { text: '浑浊', emoji: '🌫️' };
}

// -------------------- 企业微信排版优化 --------------------
function formatForWeCom(results, city) {
  let content = `## 🌅 火烧云预报 · ${city}\n`;
  content += `> 监测到共有 **${results.length}** 个模型概率超过阈值 (${THRESHOLD})\n\n`;

  const groups = groupByEvent(results);

  for (const event in groups) {
    content += `### 📅 ${EVENT_NAMES[event] || event}\n`;
    groups[event].forEach(item => {
      const q = getQualityInfo(item.quality);
      const a = getAodInfo(item.tb_aod);
      const progress = getProgressBar(item.quality);
      const timeStr = item.tb_event_time.split(' ')[1] || item.tb_event_time; // 只取时间部分

      content += `> **模型：${item.model}**\n`;
      content += `> 概率：<font color="${q.color}">${q.emoji} ${q.text} ${(item.quality * 100).toFixed(0)}%</font>\n`;
      content += `> 进度：\`${progress}\`\n`;
      content += `> 时间：\`${timeStr}\` | AOD：${a.emoji}${a.text}\n`;
      content += `>\n`;
    });
  }

  content += `--- \n`;
  content += `<font color="comment">数据更新于：${new Date().toLocaleString('zh-CN')} | SunsetBot</font>`;
  return content;
}

// -------------------- Telegram 排版优化 --------------------
function formatForTelegram(results, city) {
  let content = `<b>🌅 火烧云预报 · ${city}</b>\n`;
  content += `<code>Threshold: ${THRESHOLD}</code>\n\n`;

  const groups = groupByEvent(results);

  for (const event in groups) {
    content += `<b>────── ${EVENT_NAMES[event] || event} ──────</b>\n`;
    groups[event].forEach(item => {
      const q = getQualityInfo(item.quality);
      const a = getAodInfo(item.tb_aod);
      const progress = getProgressBar(item.quality);
      const timeStr = item.tb_event_time.split(' ')[1] || item.tb_event_time;

      content += `<b>${item.model} Model</b> ${q.emoji}\n`;
      content += `<code>[${progress}] ${(item.quality * 100).toFixed(0)}%</code>\n`;
      content += `✨ 质量: <b>${q.text}</b>\n`;
      content += `⏰ 时间: <code>${timeStr}</code>\n`;
      content += `💨 AOD : <code>${item.tb_aod} (${a.text})</code>\n\n`;
    });
  }

  content += `🔗 <i>Data Source: SunsetBot.top</i>`;
  return content;
}

// -------------------- 逻辑处理工具 --------------------

function groupByEvent(results) {
  return results.reduce((acc, curr) => {
    if (!acc[curr.event]) acc[curr.event] = [];
    acc[curr.event].push(curr);
    return acc;
  }, {});
}

function parseQuality(qualityStr) {
  if (!qualityStr) return 0;
  const match = qualityStr.match(/[\d.]+/);
  return match ? parseFloat(match[0]) : 0;
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function querySunsetDataWithRetry(city, event, model, retryCount = 0) {
  const queryId = Math.floor(1000000 + Math.random() * 9000000).toString();
  const url = `https://sunsetbot.top/?query_id=${queryId}&intend=select_city&query_city=${encodeURIComponent(city)}&event_date=None&event=${event}&times=None&model=${model}`;

  try {
    const response = await axios.get(url, {
      headers: { 'user-agent': 'Mozilla/5.0', 'x-requested-with': 'XMLHttpRequest' },
      timeout: 10000
    });
    if (response.data && response.data.status === 'ok') return response.data;
    if (retryCount < MAX_RETRIES) {
      await sleep(RETRY_DELAY);
      return querySunsetDataWithRetry(city, event, model, retryCount + 1);
    }
    return null;
  } catch (error) {
    if (retryCount < MAX_RETRIES) {
      await sleep(RETRY_DELAY);
      return querySunsetDataWithRetry(city, event, model, retryCount + 1);
    }
    return null;
  }
}

async function sendWeChat(content) {
  if (!WX_WEBHOOK_URL) return;
  try {
    await axios.post(WX_WEBHOOK_URL, { msgtype: "markdown", markdown: { content } });
    console.log('✅ WeCom Sent');
  } catch (e) { console.error('❌ WeCom Fail', e.message); }
}

async function sendTelegram(content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return;
  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_CHAT_ID,
      text: content,
      parse_mode: 'HTML',
      disable_web_page_preview: true
    });
    console.log('✅ Telegram Sent');
  } catch (e) { console.error('❌ TG Fail', e.message); }
}

// -------------------- 执行入口 --------------------
async function main() {
  console.log(`🚀 Start Monitoring: ${CITY}...`);
  const notifyResults = [];

  for (const model of MODELS) {
    for (const event of EVENTS) {
      const data = await querySunsetDataWithRetry(CITY, event, model);
      if (data) {
        const quality = parseQuality(data.tb_quality);
        if (quality >= THRESHOLD) {
          notifyResults.push({
            model, event, quality,
            tb_quality: data.tb_quality,
            tb_event_time: data.tb_event_time,
            tb_aod: data.tb_aod
          });
        }
      }
      await sleep(QUERY_DELAY);
    }
  }

  if (notifyResults.length > 0) {
    const wxMsg = formatForWeCom(notifyResults, CITY);
    const tgMsg = formatForTelegram(notifyResults, CITY);
    await sendWeChat(wxMsg);
    await sendTelegram(tgMsg);
  } else {
    console.log('💤 No high probability detected.');
  }
}

main().catch(console.error);
