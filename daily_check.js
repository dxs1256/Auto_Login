/*
 青龙火烧云概率监控脚本 (多通道通知版) v2.22
 功能：监控日出日落火烧云概率，支持企业微信机器人和Telegram通知
 作者：Situ
 更新时间：2026-04-21
 改动：优化代码结构、添加重试机制、完善通知排版和说明
*/

const axios = require('axios');

// ==================== 配置区 ====================
// 基础配置
const CITY = process.env.SUNSET_CITY || '广东省-深圳';
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5');
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS'];
const EVENTS = ['set_2', 'set_1', 'rise_2'];
const TIMEZONE = process.env.SUNSET_TIMEZONE || 'Asia/Shanghai'; // 时区设置

// 重试配置
const MAX_RETRIES = parseInt(process.env.SUNSET_MAX_RETRIES || '3', 10);
const RETRY_DELAY = parseInt(process.env.SUNSET_RETRY_DELAY || '2000', 10); // ms
const QUERY_DELAY = parseInt(process.env.SUNSET_QUERY_DELAY || '1000', 10); // 请求间隔 ms

// 通道配置 (为空则不发送)
const WX_WEBHOOK_URL = process.env.WX_WEBHOOK_URL || '';
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || '';
const TG_CHAT_ID = process.env.TG_CHAT_ID || '';

// ==================== 常量 ====================
const API_BASE = 'https://sunsetbot.top/';
const EVENT_NAMES = {
  'set_1': '今天落日',
  'set_2': '明天落日',
  'rise_1': '明天日出',
  'rise_2': '后天日出'
};

const QUALITY_LEVELS = {
  excellent: { threshold: 0.8, text: '极佳', emoji: '🔥', desc: '非常适合观赏！' },
  good: { threshold: 0.6, text: '很好', emoji: '✨', desc: '适合观赏' },
  normal: { threshold: 0.4, text: '一般', emoji: '☀️', desc: '可以尝试观赏' },
  poor: { threshold: 0.2, text: '较差', emoji: '🌤️', desc: '观赏效果不佳' },
  none: { threshold: 0, text: '不烧', emoji: '❌', desc: '不建议观赏' }
};

const AOD_LEVELS = {
  low: { threshold: 0.15, text: '优', emoji: '🌟', desc: '空气通透' },
  medium: { threshold: 0.3, text: '良', emoji: '👍', desc: '空气一般' },
  high: { threshold: Infinity, text: '差', emoji: '🌫️', desc: '空气浑浊' }
};

let todaySunsetNotified = false;

// ==================== 工具函数 ====================

function generateQueryId() {
  return Math.floor(1000000 + Math.random() * 9000000).toString();
}

function parseQuality(qualityStr) {
  if (!qualityStr) return 0;
  const match = qualityStr.match(/[\d.]+/);
  return match ? parseFloat(match[0]) : 0;
}

function getQualityInfo(quality) {
  if (quality >= QUALITY_LEVELS.excellent.threshold) return QUALITY_LEVELS.excellent;
  if (quality >= QUALITY_LEVELS.good.threshold) return QUALITY_LEVELS.good;
  if (quality >= QUALITY_LEVELS.normal.threshold) return QUALITY_LEVELS.normal;
  if (quality >= QUALITY_LEVELS.poor.threshold) return QUALITY_LEVELS.poor;
  return QUALITY_LEVELS.none;
}

function getAodInfo(aod) {
  if (aod < AOD_LEVELS.low.threshold) return AOD_LEVELS.low;
  if (aod < AOD_LEVELS.medium.threshold) return AOD_LEVELS.medium;
  return AOD_LEVELS.high;
}

function formatTimeForDisplay(timeStr) {
  if (!timeStr) return '未知';
  // timeStr 格式: 2026-04-22 19:10:05
  // 添加时区说明
  return `${timeStr} (${TIMEZONE})`;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// -------------------- 数据查询 --------------------

async function querySunsetDataWithRetry(city, event, model, retryCount = 0) {
  const queryId = generateQueryId();
  const encodedCity = encodeURIComponent(city);
  const url = `${API_BASE}?query_id=${queryId}&intend=select_city&query_city=${encodedCity}&event_date=None&event=${event}&times=None&model=${model}`;

  try {
    console.log(`  📡 [${model}-${EVENT_NAMES[event]}] 第${retryCount + 1}次尝试...`);
    const response = await axios.get(url, {
      headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
      },
      timeout: 15000
    });

    if (response.data && response.data.status === 'ok') {
      console.log(`  ✅ [${model}-${EVENT_NAMES[event]}] 查询成功`);
      console.log(`     概率: ${response.data.tb_quality} | 时间: ${response.data.tb_event_time} | AOD: ${response.data.tb_aod}`);
      return response.data;
    }

    if (retryCount < MAX_RETRIES - 1) {
      console.log(`  ⚠️ [${model}-${EVENT_NAMES[event]}] 返回状态异常，${RETRY_DELAY/1000}秒后重试...`);
      await sleep(RETRY_DELAY);
      return querySunsetDataWithRetry(city, event, model, retryCount + 1);
    }

    console.log(`  ❌ [${model}-${EVENT_NAMES[event]}] 超过最大重试次数`);
    return null;
  } catch (error) {
    if (retryCount < MAX_RETRIES - 1) {
      console.log(`  ⚠️ [${model}-${EVENT_NAMES[event]}] ${error.message}，${RETRY_DELAY/1000}秒后重试...`);
      await sleep(RETRY_DELAY);
      return querySunsetDataWithRetry(city, event, model, retryCount + 1);
    }
    console.log(`  ❌ [${model}-${EVENT_NAMES[event]}] 查询失败 (已重试${MAX_RETRIES}次): ${error.message}`);
    return null;
  }
}

// -------------------- 格式化逻辑（统一抽象） --------------------

function formatResultItem(data, platform) {
  const qualityInfo = getQualityInfo(data.quality);
  const aodInfo = getAodInfo(data.tb_aod);
  const modelName = data.model;
  const eventTime = formatTimeForDisplay(data.tb_event_time);
  const aod = parseFloat(data.tb_aod).toFixed(3);

  if (platform === 'wecom') {
    return {
      model: modelName,
      quality: data.quality,
      qualityText: qualityInfo.text,
      qualityEmoji: qualityInfo.emoji,
      qualityDesc: qualityInfo.desc,
      eventTime: eventTime,
      aod: aod,
      aodText: aodInfo.text,
      aodEmoji: aodInfo.emoji,
      aodDesc: aodInfo.desc
    };
  } else {
    return {
      model: modelName,
      quality: data.quality,
      qualityText: qualityInfo.text,
      qualityEmoji: qualityInfo.emoji,
      qualityDesc: qualityInfo.desc,
      eventTime: eventTime,
      aod: aod,
      aodText: aodInfo.text,
      aodEmoji: aodInfo.emoji,
      aodDesc: aodInfo.desc
    };
  }
}

function groupByEvent(results) {
  const groups = {};
  results.forEach(r => {
    if (!groups[r.event]) groups[r.event] = [];
    groups[r.event].push(r);
  });
  return groups;
}

// -------------------- 平台特定格式化 --------------------

function formatForWeCom(results, city) {
  const lines = [`## 🌅 ${city} 火烧云预警`];
  lines.push(`> 📍 城市: ${city} | 🔔 阈值: ${THRESHOLD} | ⏰ 时区: ${TIMEZONE}`);
  lines.push('');
  lines.push('---');

  const eventGroups = groupByEvent(results);

  Object.keys(eventGroups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    lines.push(`\n### 📆 ${eventName}`);
    lines.push('');

    eventGroups[event].forEach(data => {
      const item = formatResultItem(data, 'wecom');
      const color = data.quality >= 0.6 ? 'warning' : (data.quality >= 0.4 ? 'info' : 'comment');

      lines.push(`**${item.model}**`);
      lines.push(`> ${item.qualityEmoji} 概率: <font color="${color}">${item.qualityText} (${data.quality})</font>`);
      lines.push(`> 💨 AOD: ${item.aod}${item.aodEmoji} ${item.aodText} - ${item.aodDesc}`);
      lines.push(`> ⏰ 时间: ${item.eventTime}`);
      lines.push(`> 💡 说明: ${item.qualityDesc}`);
      lines.push('');
    });
  });

  lines.push('---');
  lines.push('> 🔗 数据来源: sunsetbot.top | 仅供娱乐参考');

  return lines.join('\n');
}

function formatForTelegram(results, city) {
  const lines = [];
  lines.push(`🌅 <b>${city} 火烧云预警</b>`);
  lines.push(`📍 城市: ${city} | 🔔 阈值: ${THRESHOLD} | ⏰ 时区: ${TIMEZONE}`);
  lines.push('');

  const eventGroups = groupByEvent(results);

  Object.keys(eventGroups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    lines.push(`📆 <u><b>${eventName}</b></u>`);
    lines.push('');

    eventGroups[event].forEach(data => {
      const item = formatResultItem(data, 'tg');

      lines.push(`🔹 <b>${item.model}</b>`);
      lines.push(`   ${item.qualityEmoji} 概率: <b>${item.qualityText}</b> (${data.quality}) - ${item.qualityDesc}`);
      lines.push(`   💨 AOD: ${item.aod}${item.aodEmoji} ${item.aodText} - ${item.aodDesc}`);
      lines.push(`   ⏰ 时间: ${item.eventTime}`);
      lines.push('');
    });
  });

  lines.push('---');
  lines.push('🔗 数据来源: sunsetbot.top | 仅供娱乐参考');

  return lines.join('\n');
}

// -------------------- 发送通道 --------------------

async function sendWeChat(content) {
  if (!WX_WEBHOOK_URL) return;
  try {
    await axios.post(WX_WEBHOOK_URL, {
      msgtype: "markdown",
      markdown: { content }
    });
    console.log('✅ 企业微信通知已发送');
  } catch (e) {
    console.log(`⚠️ 企业微信发送失败: ${e.message}`);
  }
}

async function sendTelegram(content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return;
  try {
    const url = `https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`;
    await axios.post(url, {
      chat_id: TG_CHAT_ID,
      text: content,
      parse_mode: 'HTML',
      disable_web_page_preview: true
    });
    console.log('✅ Telegram 通知已发送');
  } catch (e) {
    console.log(`⚠️ Telegram 发送失败: ${e.message}`);
  }
}

// -------------------- 主程序 --------------------

async function main() {
  console.log('');
  console.log('==================== 火烧云监控启动 ====================');
  console.log(`📍 城市: ${CITY}`);
  console.log(`🔔 阈值: ${THRESHOLD} | ⏰ 时区: ${TIMEZONE}`);
  console.log(`📊 模型: ${MODELS.join(', ')} | 📅 事件: ${EVENTS.map(e => EVENT_NAMES[e]).join(', ')}`);
  console.log(`🔄 重试: 最多${MAX_RETRIES}次 | 请求间隔: ${QUERY_DELAY}ms`);
  console.log('');

  if (WX_WEBHOOK_URL) console.log('🔔 企业微信通知: 已启用');
  if (TG_BOT_TOKEN) console.log('✈️ Telegram通知: 已启用');
  console.log('');

  const notifyResults = [];

  for (const model of MODELS) {
    for (const event of EVENTS) {
      console.log(`\n🔍 查询: ${model} - ${EVENT_NAMES[event]}...`);
      const data = await querySunsetDataWithRetry(CITY, event, model);

      if (data) {
        const quality = parseQuality(data.tb_quality);
        const qualityInfo = getQualityInfo(quality);
        const aodInfo = getAodInfo(data.tb_aod);

        console.log(`   📊 概率: ${quality} (${qualityInfo.text})`);
        console.log(`   💨 AOD: ${data.tb_aod} (${aodInfo.text})`);
        console.log(`   ⏰ 时间: ${data.tb_event_time}`);

        if (quality >= THRESHOLD) {
          if (event === 'set_1' && todaySunsetNotified) {
            console.log(`   ⏭️ 今天落日已通知，跳过`);
          } else {
            console.log(`   🎯 超过阈值 ${THRESHOLD}，加入通知列表`);
            notifyResults.push({
              model, event, quality,
              tb_quality: data.tb_quality,
              tb_event_time: data.tb_event_time,
              tb_aod: data.tb_aod
            });
            if (event === 'set_1') todaySunsetNotified = true;
          }
        } else {
          console.log(`   ⏳ 未超过阈值 ${THRESHOLD}，不通知`);
        }
      }

      if (QUERY_DELAY > 0) {
        await sleep(QUERY_DELAY);
      }
    }
  }

  console.log('\n========================================================');
  console.log(`📊 查询完成，共 ${notifyResults.length} 条数据超过阈值`);

  if (notifyResults.length > 0) {
    console.log('\n📱 正在推送通知...');

    if (WX_WEBHOOK_URL) {
      const wxContent = formatForWeCom(notifyResults, CITY);
      await sendWeChat(wxContent);
    }

    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      const tgContent = formatForTelegram(notifyResults, CITY);
      await sendTelegram(tgContent);
    }

    console.log('\n✅ 通知推送完成');
  } else {
    console.log('\n💤 无高概率数据，不发送通知');
  }

  console.log('==================== 监控结束 ====================');
}

main().catch(console.error);
