/*
  火烧云概率监控脚本 v2.60
  功能：监控日出日落火烧云概率，支持 PushPlus 与 Telegram 通知
  更新时间：2026-05-27
  改动：
    1. 通知窗口从 24 小时缩短为 12 小时
    2. 新增趋势标识功能（上升/下降/稳定）
    3. 概率下降时也会通知，提供完整信息流
*/

const axios = require('axios');

// ==================== 配置区 ====================

// 基础配置（非敏感，直接写死）
const CITY = process.env.SUNSET_CITY || '十堰 - 茅箭区';
const THRESHOLD = 0.5;                    // 触发阈值 50%
const MODELS = ['EC', 'GFS'];             // 气象模型
const EVENTS = ['set_1', 'set_2', 'rise_1'];  // 今天落日，明天落日，明天日出
const TIMEZONE = 'Asia/Shanghai';         // 时区
const NOTIFY_WINDOW_HOURS = 12;           // 通知窗口 12 小时
const SEND_DECLINE = true;                // 概率下降也通知

// 重试配置
const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;                 // 2 秒
const QUERY_DELAY = 1000;                 // 1 秒

// 通知配置（敏感，用环境变量）
const PUSHPLUS_TOKEN = process.env.PUSHPLUS_TOKEN || '';
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

const trendState = {};
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

function getTrendInfo(current, previous) {
  if (previous === null || previous === undefined) {
    return { symbol: '', text: '首次监测', direction: 0 };
  }
  
  const diff = current - previous;
  
  if (diff >= 0.1) {
    return { symbol: '↗️', text: '上升', direction: 1 };
  } else if (diff <= -0.1) {
    return { symbol: '↘️', text: '下降', direction: -1 };
  } else {
    return { symbol: '➡️', text: '稳定', direction: 0 };
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

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function isEventPassed(eventTime) {
  if (!eventTime) return true;
  const now = new Date();
  
  let eventDate;
  const timeStr = String(eventTime).trim();
  
  const matchFull = timeStr.match(/(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
  if (matchFull) {
    const [, year, month, day, hour, minute] = matchFull;
    eventDate = new Date(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${hour.padStart(2, '0')}:${minute.padStart(2, '0')}:00${getTimezoneOffset()}`);
  } else {
    const matchShort = timeStr.match(/(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})/);
    if (matchShort) {
      const [, month, day, hour, minute] = matchShort;
      const year = now.getFullYear();
      eventDate = new Date(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${hour.padStart(2, '0')}:${minute.padStart(2, '0')}:00${getTimezoneOffset()}`);
    } else {
      eventDate = new Date(timeStr);
    }
  }
  
  if (isNaN(eventDate.getTime())) {
    console.log(`  ⚠️ 无法解析时间：${timeStr}`);
    return false;
  }
  
  if (eventDate < now) {
    return true;
  }
  
  const hoursUntilEvent = (eventDate - now) / (1000 * 60 * 60);
  if (hoursUntilEvent > NOTIFY_WINDOW_HOURS) {
    console.log(`  ⏭️ "${timeStr}" 距离事件还有${hoursUntilEvent.toFixed(1)}小时，超过通知窗口 (${NOTIFY_WINDOW_HOURS}小时)，跳过`);
    return true;
  }
  
  return false;
}

function getTimezoneOffset() {
  const tzMap = {
    'Asia/Shanghai': '+08:00',
    'Asia/Chongqing': '+08:00',
    'UTC': '+00:00',
    'America/New_York': '-05:00',
    'America/Los_Angeles': '-08:00',
    'Europe/London': '+00:00',
    'Asia/Tokyo': '+09:00'
  };
  return tzMap[TIMEZONE] || '+08:00';
}

// ==================== 核心排版逻辑 ====================

function formatForWeCom(results, city) {
  const lines = [];
  lines.push(`📍 ${city} | 🔔 阈值：${THRESHOLD} | ⏰ ${TIMEZONE}`);
  lines.push('');

  const groups = groupByEvent(results);

  Object.keys(groups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    const firstData = groups[event][0];
    lines.push(`📆 ${eventName} ${firstData.tb_event_time}`);

    groups[event].forEach(data => {
      const qInfo = getQualityInfo(data.quality);
      const aInfo = getAodInfo(data.tb_aod);
      const trendInfo = data.trendInfo;

      lines.push(`🔹 ${data.model}`);
      lines.push(`   ${qInfo.emoji} 观赏指数：${qInfo.text} (${data.quality.toFixed(3)})  ${trendInfo.symbol}${trendInfo.text}`);
      if (trendInfo.direction === -1 && SEND_DECLINE) {
        lines.push(`   ⚠️ 概率下降，可能看不到，降低期望值`);
      } else {
        lines.push(`   ${qInfo.desc}`);
      }
      lines.push(`   🌬️ 空气质量：${aInfo.text} (${parseFloat(data.tb_aod).toFixed(3)}) - ${aInfo.desc}`);
    });
    lines.push('');
  });

  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间：${now}`);
  lines.push('🔗 数据来源：sunsetbot.top | 仅供娱乐参考');

  return lines.join('\n');
}

function formatForTelegram(results, city) {
  const lines = [];
  lines.push(`📍 <b>${city}</b> | 🔔 阈值：<b>${THRESHOLD}</b> | ⏰ ${TIMEZONE}`);
  lines.push('');

  const groups = groupByEvent(results);

  Object.keys(groups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    const firstData = groups[event][0];
    lines.push(`📆 <b>${eventName}</b> ${firstData.tb_event_time}`);

    groups[event].forEach(data => {
      const qInfo = getQualityInfo(data.quality);
      const aInfo = getAodInfo(data.tb_aod);
      const trendInfo = data.trendInfo;

      lines.push(`🔹 <b>${data.model}</b>`);
      lines.push(`   ${qInfo.emoji} 概率：<b>${data.quality.toFixed(3)} ${qInfo.text}</b> ${trendInfo.symbol}${trendInfo.text}`);
      if (trendInfo.direction === -1 && SEND_DECLINE) {
        lines.push(`   ⚠️ <i>概率下降，建议降低期望</i>`);
      } else {
        lines.push(`   ${qInfo.desc}`);
      }
      lines.push(`   💨 AOD: ${parseFloat(data.tb_aod).toFixed(3)} ${aInfo.emoji}${aInfo.text} - ${aInfo.desc}`);
    });
    lines.push('');
  });

  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间：${now}`);
  lines.push('🔗 数据来源：sunsetbot.top | 仅供娱乐参考');

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

async function sendPushPlus(content) {
  if (!PUSHPLUS_TOKEN) return;
  try {
    await axios.post('http://www.pushplus.plus/send', {
      token: PUSHPLUS_TOKEN,
      title: '火烧云预警',
      content: content,
      type: 'markdown'
    });
    console.log('✅ PushPlus 通知推送成功');
  } catch (e) {
    console.log(`⚠️ PushPlus 发送失败：${e.message}`);
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
    console.log(`⚠️ Telegram 发送失败：${e.message}`);
  }
}

// ==================== 主程序入口 ====================

async function main() {
  console.log('\n==================== 火烧云监控启动 ====================');
  console.log(`📍 城市：${CITY} | 🔔 阈值：${THRESHOLD} | ⏰ 时区：${TIMEZONE}`);
  console.log(`📊 模型：${MODELS.join(', ')} | 📅 事件：${EVENTS.map(e => EVENT_NAMES[e]).join(', ')}`);
  console.log(`🔔 通知窗口：${NOTIFY_WINDOW_HOURS}小时 | 📉 下降通知：${SEND_DECLINE ? '开启' : '关闭'}`);
  
  if (PUSHPLUS_TOKEN) console.log('📲 PushPlus 通知：已启用');
  if (TG_BOT_TOKEN) console.log('✈️ Telegram 通知：已启用');
  console.log('--------------------------------------------------------');

  const notifyResults = [];

  for (const model of MODELS) {
    for (const event of EVENTS) {
      const data = await querySunsetDataWithRetry(CITY, event, model);

      if (data) {
        const quality = parseQuality(data.tb_quality);
        const qInfo = getQualityInfo(quality);
        
        const stateKey = `${model}_${event}`;
        const previousQuality = trendState[stateKey] || null;
        const trendInfo = getTrendInfo(quality, previousQuality);
        
        trendState[stateKey] = quality;

        console.log(`  ✅ 成功 -> 概率：${quality} (${qInfo.text}) ${trendInfo.symbol}${trendInfo.text} | 时间：${data.tb_event_time} | AOD: ${data.tb_aod}`);

        if (isEventPassed(data.tb_event_time)) {
          console.log(`  ⏭️ "${EVENT_NAMES[event]}" 时间已过 (${data.tb_event_time})，跳过`);
        } else {
          const shouldNotify = quality >= THRESHOLD || (SEND_DECLINE && trendInfo.direction === -1);
          
          if (shouldNotify) {
            if (event === 'set_1' && todaySunsetNotified) {
              console.log(`  ⏭️ "今天落日"已达标过，跳过重复预警`);
            } else {
              console.log(`  🎯 加入推送队列 (趋势：${trendInfo.symbol}${trendInfo.text})`);
              notifyResults.push({
                model, event, quality,
                tb_quality: data.tb_quality,
                tb_event_time: data.tb_event_time,
                tb_aod: data.tb_aod,
                trendInfo
              });
              if (event === 'set_1') todaySunsetNotified = true;
            }
          } else {
            console.log(`  ⏳ 未达标 (需 >= ${THRESHOLD})，忽略`);
          }
        }
      } else {
        console.log(`  ⏳ 未达标 (需 >= ${THRESHOLD})，忽略`);
      }

      if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
    }
  }

  console.log('\n======================== 数据汇总 ========================');
  console.log(`📊 共筛选出 ${notifyResults.length} 条数据`);

  if (notifyResults.length > 0) {
    console.log('📱 正在推送至各个终端...');
    
    if (PUSHPLUS_TOKEN) {
      const ppContent = formatForWeCom(notifyResults, CITY);
      await sendPushPlus(ppContent);
    }

    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      const tgContent = formatForTelegram(notifyResults, CITY);
      await sendTelegram(tgContent);
    }
    
  } else {
    console.log('💤 当日无数据或全部超过通知窗口，不发送推送');
  }

  console.log('==================== 本次监控结束 ====================\n');
}

main().catch(console.error);
