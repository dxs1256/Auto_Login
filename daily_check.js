/*
 火烧云概率监控脚本 v2.50
 功能：监控日出日落火烧云概率，支持扁平化企业微信与仪表盘级Telegram通知
 更新时间：2026-04-21
 改动：重构消息排版机制，解决企业微信解析异常问题，提升TG端数据美观度
*/

const axios = require('axios');

// ==================== 配置区 ====================
// 基础配置
const CITY = process.env.SUNSET_CITY || '广东省-深圳';
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5');
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS'];
const EVENTS = ['set_1', 'set_2', 'rise_1']; // 常用: set_1今天落日, set_2明天落日, rise_1明天日出
const TIMEZONE = process.env.SUNSET_TIMEZONE || 'Asia/Shanghai'; 

// 重试配置
const MAX_RETRIES = parseInt(process.env.SUNSET_MAX_RETRIES || '3', 10);
const RETRY_DELAY = parseInt(process.env.SUNSET_RETRY_DELAY || '2000', 10); // ms
const QUERY_DELAY = parseInt(process.env.SUNSET_QUERY_DELAY || '1000', 10); // 请求间隔 ms

// 通道配置 (为空则不发送)
const WX_WEBHOOK_URL = process.env.WX_WEBHOOK_URL || '';
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || '';
const TG_CHAT_ID = process.env.TG_CHAT_ID || '';

// ==================== 常量定义 ====================
const API_BASE = 'https://sunsetbot.top/';

const EVENT_NAMES = {
  'set_1': '今天落日',
  'set_2': '明天落日',
  'rise_1': '明天日出',
  'rise_2': '后天日出'
};

const QUALITY_LEVELS = {
  excellent: { threshold: 0.8, text: '极佳', emoji: '🔥', color: 'warning', desc: '绝对值得出门观赏！' },
  good: { threshold: 0.6, text: '很好', emoji: '✨', color: 'warning', desc: '非常适合观赏，不要错过' },
  normal: { threshold: 0.4, text: '一般', emoji: '☀️', color: 'info', desc: '可以碰碰运气' },
  poor: { threshold: 0.2, text: '较差', emoji: '🌤️', color: 'comment', desc: '大概率不烧，随缘' },
  none: { threshold: 0, text: '不烧', emoji: '❌', color: 'comment', desc: '洗洗睡吧' }
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
  const val = parseFloat(aod);
  if (val < 0.15) return { text: '优', emoji: '💎', desc: '空气极其通透' };
  if (val < 0.3) return { text: '良', emoji: '🌿', desc: '空气一般' };
  return { text: '差', emoji: '🌫️', desc: '空气浑浊' };
}

function groupByEvent(results) {
  const groups = {};
  results.forEach(r => {
    if (!groups[r.event]) groups[r.event] = [];
    groups[r.event].push(r);
  });
  return groups;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ==================== 核心排版逻辑 ====================

// 1. 企业微信排版 (通俗易懂版)
function formatForWeCom(results, city) {
  const lines = [];
  lines.push(`📍 ${city} | 🔔 阈值: ${THRESHOLD} | ⏰ ${TIMEZONE}`);
  lines.push('');

  const groups = groupByEvent(results);

  Object.keys(groups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    const firstData = groups[event][0];
    lines.push(`📆 ${eventName} ${firstData.tb_event_time}`);

    groups[event].forEach(data => {
      const qInfo = getQualityInfo(data.quality);
      const aInfo = getAodInfo(data.tb_aod);

      lines.push(`🔹 ${data.model}`);
      lines.push(`   ${qInfo.emoji} 观赏指数: ${qInfo.text} (${data.quality.toFixed(3)})  - ${qInfo.desc}`);
      lines.push(`   🌬️ 空气质量: ${aInfo.text} (${parseFloat(data.tb_aod).toFixed(3)}) - ${aInfo.desc}`);
    });
    lines.push('');
  });

  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间: ${now}`);
  lines.push('🔗 数据来源: sunsetbot.top | 仅供娱乐参考');

  return lines.join('\n');
}

// 2. Telegram排版 (等宽代码块与HTML混合的仪表盘设计)
function formatForTelegram(results, city) {
  const lines = [];
  lines.push(`📍 <b>${city}</b> | 🔔 阈值: <b>${THRESHOLD}</b> | ⏰ ${TIMEZONE}`);
  lines.push('');

  const groups = groupByEvent(results);

  Object.keys(groups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    const firstData = groups[event][0];
    lines.push(`📆 <b>${eventName}</b> ${firstData.tb_event_time}`);

    groups[event].forEach(data => {
      const qInfo = getQualityInfo(data.quality);
      const aInfo = getAodInfo(data.tb_aod);

      lines.push(`🔹 <b>${data.model}</b>`);
      lines.push(`   ${qInfo.emoji} 概率: <b>${data.quality.toFixed(3)} ${qInfo.text}</b> | ${qInfo.desc}`);
      lines.push(`   💨 AOD: ${parseFloat(data.tb_aod).toFixed(3)} ${aInfo.emoji}${aInfo.text} - ${aInfo.emoji === '💎' ? '空气极其通透' : aInfo.emoji === '🌿' ? '空气一般' : '空气浑浊'}`);
    });
    lines.push('');
  });

  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间: ${now}`);
  lines.push('🔗 数据来源: sunsetbot.top | 仅供娱乐参考');

  return lines.join('\n');
}

// ==================== 数据查询 ====================

async function querySunsetDataWithRetry(city, event, model, retryCount = 0) {
  const queryId = generateQueryId();
  const encodedCity = encodeURIComponent(city);
  const url = `${API_BASE}?query_id=${queryId}&intend=select_city&query_city=${encodedCity}&event_date=None&event=${event}&times=None&model=${model}`;

  try {
    console.log(`  📡 [${model}-${EVENT_NAMES[event]}] 第${retryCount + 1}次查询...`);
    const response = await axios.get(url, {
      headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
      },
      timeout: 15000
    });

    if (response.data && response.data.status === 'ok') {
      return response.data;
    }

    throw new Error('返回状态异常或数据为空');
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

// ==================== 发送通道 ====================

async function sendWeChat(content) {
  if (!WX_WEBHOOK_URL) return;
  try {
    await axios.post(WX_WEBHOOK_URL, {
      msgtype: "markdown",
      markdown: { content }
    });
    console.log('✅ 企业微信通知推送成功');
  } catch (e) {
    console.log(`⚠️ 企业微信发送失败: ${e.message}`);
  }
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
    console.log('✅ Telegram 通知推送成功');
  } catch (e) {
    console.log(`⚠️ Telegram 发送失败: ${e.message}`);
  }
}

// ==================== 主程序入口 ====================

async function main() {
  console.log('\n==================== 火烧云监控启动 ====================');
  console.log(`📍 城市: ${CITY} | 🔔 阈值: ${THRESHOLD} | ⏰ 时区: ${TIMEZONE}`);
  console.log(`📊 模型: ${MODELS.join(', ')} | 📅 事件: ${EVENTS.map(e => EVENT_NAMES[e]).join(', ')}`);
  
  if (WX_WEBHOOK_URL) console.log('🔔 企业微信通知: 已启用');
  if (TG_BOT_TOKEN) console.log('✈️ Telegram通知: 已启用');
  console.log('--------------------------------------------------------');

  const notifyResults = [];

  for (const model of MODELS) {
    for (const event of EVENTS) {
      const data = await querySunsetDataWithRetry(CITY, event, model);

      if (data) {
        const quality = parseQuality(data.tb_quality);
        const qInfo = getQualityInfo(quality);

        console.log(`  ✅ 成功 -> 概率: ${quality} (${qInfo.text}) | 时间: ${data.tb_event_time} | AOD: ${data.tb_aod}`);

        if (quality >= THRESHOLD) {
          if (event === 'set_1' && todaySunsetNotified) {
            console.log(`  ⏭️ "今天落日"已达标过，跳过重复预警`);
          } else {
            console.log(`  🎯 达标！加入推送队列`);
            notifyResults.push({
              model, event, quality,
              tb_quality: data.tb_quality,
              tb_event_time: data.tb_event_time,
              tb_aod: data.tb_aod
            });
            if (event === 'set_1') todaySunsetNotified = true;
          }
        } else {
          console.log(`  ⏳ 未达标 (需 >= ${THRESHOLD})，忽略`);
        }
      }

      if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
    }
  }

  console.log('\n======================== 数据汇总 ========================');
  console.log(`📊 共筛选出 ${notifyResults.length} 条高概率数据`);

  if (notifyResults.length > 0) {
    console.log('📱 正在推送至各个终端...');
    
    if (WX_WEBHOOK_URL) {
      const wxContent = formatForWeCom(notifyResults, CITY);
      await sendWeChat(wxContent);
    }

    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      const tgContent = formatForTelegram(notifyResults, CITY);
      await sendTelegram(tgContent);
    }
    
  } else {
    console.log('💤 当日无惊艳天象预警，不发送推送骚扰');
  }

  console.log('==================== 本次监控结束 ====================\n');
}

main().catch(console.error);
