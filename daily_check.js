/*
火烧云概率监控脚本（修补版 v3.0，基于 dxs1256/Auto_Login daily_check.js v2.60）
运行环境：GitHub Actions（ubuntu-latest + Node 20）
本次修补内容（对应代码审查报告）：
  1. 状态持久化到 state.json（方案 B：提交回仓库），趋势与去重跨运行生效
  2. 状态带 date 字段，北京时间跨天自动重置去重表（trendState 保留，跨天概率可比）
  3. 去重改为「事件:目标日期」粒度，set_1/set_2/rise_1 一天内不重复推送
  4. 只有至少一个通知通道发送成功才写入 notified（推送失败下次自动重试）
  5. 「概率下降」只在跌破阈值的哪一次推送，其余下降只记日志，避免连发
  6. 修复零值 bug：用 in 判断替代 || null，上次概率为 0 也能触发下降判定
  7. PushPlus 改用 HTTPS，token 不再明文传输
  8. Telegram 输出做 HTML 转义，避免 <、& 导致整条消息 400 拒收
  9. 查询失败与「未达标」严格区分；全部模型失败时推送里明确告知数据不可用
  10. AOD 缺失显示「未知」，不再误报为空气浑浊
  11. 两个通知通道都未配置时启动即退出，不浪费 API 查询
  12. 失败时 process.exitCode = 1，让 Actions 任务变红可被监控
*/
const axios = require('axios');
const fs = require('fs');
const path = require('path');

// ==================== 配置区 ====================
// 基础配置（非敏感，直接写死）
// 城市名归一化：sunsetbot API 不识别「A - B」带空格的连字符格式（会返回 not_found），
// 统一压成「A-B」；也支持直接写「十堰」「茅箭区」等简称（API 会自动匹配）
const RAW_CITY = process.env.SUNSET_CITY || '十堰-茅箭区';
const CITY = RAW_CITY.trim().replace(/\s*-\s*/g, '-');
const THRESHOLD = 0.5; // 触发阈值 50%
const MODELS = ['EC', 'GFS']; // 气象模型
const EVENTS = ['set_1', 'set_2', 'rise_1']; // 今天落日，明天落日，明天日出
const TIMEZONE = 'Asia/Shanghai'; // 时区
const NOTIFY_WINDOW_HOURS = 24; // 通知窗口 24 小时（注意：与原脚本头部注释矛盾，保持 24 以免 set_2 被永远过滤）
const SEND_DECLINE = true; // 概率跌破阈值时通知

// 重试配置
const MAX_RETRIES = 3; // 总尝试次数（含首次）
const RETRY_DELAY = 2000; // 重试间隔 2 秒
const QUERY_DELAY = 1000; // 相邻查询间隔 1 秒

// 通知配置（敏感，用环境变量）
const PUSHPLUS_TOKEN = process.env.PUSHPLUS_TOKEN || '';
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || '';
const TG_CHAT_ID = process.env.TG_CHAT_ID || '';

// 状态文件（方案 B：提交回仓库持久化）
const STATE_FILE = process.env.SUNSET_STATE_FILE || path.join(__dirname, 'state.json');

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
  good:      { threshold: 0.6, text: '很好', emoji: '✨', color: 'warning', desc: '非常适合观赏，不要错过' },
  normal:    { threshold: 0.4, text: '一般', emoji: '☀️', color: 'info', desc: '可以碰碰运气' },
  poor:      { threshold: 0.2, text: '较差', emoji: '🌤️', color: 'comment', desc: '大概率不烧，随缘' },
  none:      { threshold: 0,   text: '不烧', emoji: '❌', color: 'comment', desc: '洗洗睡吧' }
};

// ==================== 状态管理（方案 B 持久化） ====================
// 状态结构：{ version, date: 'YYYY-MM-DD'(北京), trendState: {模型_事件: 概率}, notified: {事件:目标日期: true} }

// 当前北京日期，格式 YYYY-MM-DD（en-CA locale 恰好输出 ISO 格式）
function getBeijingToday() {
  return new Date().toLocaleDateString('en-CA', { timeZone: TIMEZONE });
}

// 读取状态文件；日期不是今天则重置 notified（每日去重表），trendState 保留（跨天概率可比）
function loadState() {
  const today = getBeijingToday();
  const fresh = { version: 1, date: today, trendState: {}, notified: {} };
  try {
    const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    if (saved && saved.date === today) {
      // 同一天：沿用已有状态
      return {
        version: saved.version || 1,
        date: saved.date,
        trendState: (saved.trendState && typeof saved.trendState === 'object') ? saved.trendState : {},
        notified: (saved.notified && typeof saved.notified === 'object') ? saved.notified : {}
      };
    }
    // 跨天（或首次运行/文件损坏）：重置去重表，保留趋势观测基线
    console.log(`📅 状态日期为 ${saved && saved.date ? saved.date : '无'}，非今天(${today})，已重置去重表`);
    return fresh;
  } catch (_) {
    // 首次运行或文件不存在/损坏：全新状态
    console.log(`📁 无有效状态文件，使用全新状态`);
    return fresh;
  }
}

// 状态写入内存 + 立即落盘
let state = loadState();
function saveState() {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2) + '\n');
  } catch (e) {
    console.log(`⚠️ 状态文件写入失败：${e.message}`);
  }
}

// ==================== 工具函数 ====================
// 生成 7 位随机查询 ID（模拟网页端行为）
function generateQueryId() {
  return Math.floor(1000000 + Math.random() * 9000000).toString();
}

// 从 tb_quality 字符串中解析概率数值（如 "0.5123 (51%)" -> 0.5123）
function parseQuality(qualityStr) {
  if (!qualityStr) return 0;
  const match = String(qualityStr).match(/[\d.]+/);
  return match ? parseFloat(match[0]) : 0;
}

// 概率 -> 档位信息
function getQualityInfo(quality) {
  if (quality >= QUALITY_LEVELS.excellent.threshold) return QUALITY_LEVELS.excellent;
  if (quality >= QUALITY_LEVELS.good.threshold) return QUALITY_LEVELS.good;
  if (quality >= QUALITY_LEVELS.normal.threshold) return QUALITY_LEVELS.normal;
  if (quality >= QUALITY_LEVELS.poor.threshold) return QUALITY_LEVELS.poor;
  return QUALITY_LEVELS.none;
}

// AOD -> 空气质量描述；缺失/非法值显示「未知」，不再误报为空气浑浊
function getAodInfo(aod) {
  const val = parseFloat(aod);
  if (isNaN(val)) return { text: '未知', emoji: '❔', desc: '数据缺失' };
  if (val < 0.15) return { text: '优', emoji: '💎', desc: '空气极其通透' };
  if (val < 0.3) return { text: '良', emoji: '🌿', desc: '空气一般' };
  return { text: '差', emoji: '🌫️', desc: '空气浑浊' };
}

// 趋势判定：previous 为 null 表示首次观测（无历史可比）
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

// 结果按事件分组
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

// HTML 转义（用于 Telegram parse_mode: HTML，防止 <、>、& 破坏消息）
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// 时区 -> UTC 偏移字符串（仅覆盖常见时区，未知时区回退 +08:00 并告警）
function getTimezoneOffset() {
  const tzMap = {
    'Asia/Shanghai': '+08:00',
    'Asia/Chongqing': '+08:00',
    'UTC': '+00:00',
    'America/New_York': '-05:00', // 注意：不处理夏令时，夏季会偏差 1 小时
    'America/Los_Angeles': '-08:00',
    'Europe/London': '+00:00',
    'Asia/Tokyo': '+09:00'
  };
  if (!tzMap[TIMEZONE]) {
    console.log(`⚠️ 未知时区 ${TIMEZONE}，时间解析回退为 +08:00`);
  }
  return tzMap[TIMEZONE] || '+08:00';
}

// 解析 API 返回的事件时间；返回 Date 或 null（无法解析时返回 null，由调用方决定放行）
function parseEventTime(eventTime) {
  const now = new Date();
  const timeStr = String(eventTime).trim();
  const offset = getTimezoneOffset();

  // 完整格式：YYYY-M-D HH:mm[:ss]
  const matchFull = timeStr.match(/(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
  if (matchFull) {
    const [, year, month, day, hour, minute] = matchFull;
    return new Date(
      `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T` +
      `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}:00${offset}`
    );
  }

  // 短格式：M-D HH:mm（补当前年份；跨年场景会误判，属已知局限）
  const matchShort = timeStr.match(/(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})/);
  if (matchShort) {
    const [, month, day, hour, minute] = matchShort;
    const year = now.getFullYear();
    return new Date(
      `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T` +
      `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}:00${offset}`
    );
  }

  // 兜底：交给 Date 直接解析（在 UTC runner 上会按 UTC 解析，仅作最后手段）
  const d = new Date(timeStr);
  return isNaN(d.getTime()) ? null : d;
}

// 判断事件是否应跳过推送：已过期 / 超出通知窗口；无法解析时间时放行（宁可误报不可漏报）
function isEventPassed(eventTime) {
  if (!eventTime) return true;
  const now = new Date();
  const eventDate = parseEventTime(eventTime);
  if (!eventDate) {
    console.log(` ⚠️ 无法解析时间：${String(eventTime).trim()}，按未过期处理`);
    return false;
  }
  if (eventDate < now) {
    return true;
  }
  const hoursUntilEvent = (eventDate - now) / (1000 * 60 * 60);
  if (hoursUntilEvent > NOTIFY_WINDOW_HOURS) {
    console.log(` ⏭️ "${String(eventTime).trim()}" 距离事件还有${hoursUntilEvent.toFixed(1)}小时，超过通知窗口 (${NOTIFY_WINDOW_HOURS}小时)，跳过`);
    return true;
  }
  return false;
}

// 从事件时间字符串提取目标日期（YYYY-MM-DD），作为去重 key 的一部分
// 关键：set_2 今天 18:50 看到和明天 17:50 看到是两个不同事件，必须分别去重
function getEventDateKey(eventTime) {
  const m = String(eventTime).match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) {
    return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  }
  // 短格式没有年份，用解析结果补全年月日
  const d = parseEventTime(eventTime);
  if (d) {
    return d.toLocaleDateString('en-CA', { timeZone: TIMEZONE });
  }
  return 'unknown';
}

// ==================== 核心排版逻辑 ====================
// PushPlus 推送排版（纯文本，type: markdown）
function formatForPushPlus(results, city, noData) {
  const lines = [];
  if (noData) {
    lines.push(`📍 ${city}`);
    lines.push('');
    lines.push('❌ 本次所有模型查询均失败，未获取到有效数据。');
    lines.push('可能是 sunsetbot.top 服务异常或网络问题，请稍后关注下次运行。');
    lines.push('');
    lines.push('--------------------');
    const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
    lines.push(`📨 推送时间：${now}`);
    lines.push('🔗 数据来源：sunsetbot.top | 仅供娱乐参考');
    return lines.join('\n');
  }
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
      const t = data.trendInfo;
      lines.push(`🔹 ${data.model}`);
      lines.push(` ${qInfo.emoji} 观赏指数：${qInfo.text} (${data.quality.toFixed(3)}) ${t.symbol}${t.text}`);
      if (data.crossedBelow) {
        lines.push(` ⚠️ 概率跌破阈值 ${THRESHOLD}，趋势转差，降低期望值`);
      } else if (t.direction === -1) {
        lines.push(` ${qInfo.desc}`);
      } else {
        lines.push(` ${qInfo.desc}`);
      }
      lines.push(` 🌬️ 空气质量：${aInfo.text} (${parseFloat(data.tb_aod).toFixed(3)}) - ${aInfo.desc}`);
    });
    lines.push('');
  });
  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间：${now}`);
  lines.push('🔗 数据来源：sunsetbot.top | 仅供娱乐参考');
  return lines.join('\n');
}

// Telegram 推送排版（HTML，动态内容全部转义）
function formatForTelegram(results, city, noData) {
  const lines = [];
  if (noData) {
    lines.push(`📍 <b>${escapeHtml(city)}</b>`);
    lines.push('');
    lines.push('❌ 本次所有模型查询均失败，未获取到有效数据。');
    lines.push('可能是 sunsetbot.top 服务异常或网络问题，请稍后关注下次运行。');
    lines.push('--------------------');
    const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
    lines.push(`📨 推送时间：${escapeHtml(now)}`);
    lines.push(`🔗 数据来源：sunsetbot.top | 仅供娱乐参考`);
    return lines.join('\n');
  }
  lines.push(`📍 <b>${escapeHtml(city)}</b> | 🔔 阈值：<b>${THRESHOLD}</b> | ⏰ ${escapeHtml(TIMEZONE)}`);
  lines.push('');
  const groups = groupByEvent(results);
  Object.keys(groups).forEach(event => {
    const eventName = EVENT_NAMES[event] || event;
    const firstData = groups[event][0];
    lines.push(`📆 <b>${escapeHtml(eventName)}</b> ${escapeHtml(firstData.tb_event_time)}`);
    groups[event].forEach(data => {
      const qInfo = getQualityInfo(data.quality);
      const aInfo = getAodInfo(data.tb_aod);
      const t = data.trendInfo;
      lines.push(`🔹 <b>${escapeHtml(data.model)}</b>`);
      lines.push(` ${qInfo.emoji} 概率：<b>${data.quality.toFixed(3)} ${qInfo.text}</b> ${t.symbol}${t.text}`);
      if (data.crossedBelow) {
        lines.push(` ⚠️ <i>概率跌破阈值 ${THRESHOLD}，建议降低期望</i>`);
      } else {
        lines.push(` ${escapeHtml(qInfo.desc)}`);
      }
      const aodNum = isNaN(parseFloat(data.tb_aod)) ? '未知' : parseFloat(data.tb_aod).toFixed(3);
      lines.push(` 💨 AOD: ${aodNum} ${aInfo.emoji}${aInfo.text} - ${escapeHtml(aInfo.desc)}`);
    });
    lines.push('');
  });
  lines.push('--------------------');
  const now = new Date().toLocaleString('zh-CN', { timeZone: TIMEZONE });
  lines.push(`📨 推送时间：${escapeHtml(now)}`);
  lines.push(`🔗 数据来源：sunsetbot.top | 仅供娱乐参考`);
  return lines.join('\n');
}

// ==================== 数据查询 ====================
// 带重试的查询；耗尽后返回 null（区别于「未达标」）
async function querySunsetDataWithRetry(city, event, model, retryCount = 0) {
  const queryId = generateQueryId();
  const encodedCity = encodeURIComponent(city);
  const url = `${API_BASE}?query_id=${queryId}&intend=select_city&query_city=${encodedCity}&event_date=None&event=${event}&times=None&model=${model}`;
  try {
    console.log(` 📡 [${model}-${EVENT_NAMES[event]}] 第${retryCount + 1}次查询...`);
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
      console.log(` ⚠️ [${model}-${EVENT_NAMES[event]}] ${error.message}，${RETRY_DELAY / 1000}秒后重试...`);
      await sleep(RETRY_DELAY);
      return querySunsetDataWithRetry(city, event, model, retryCount + 1);
    }
    // 注意：总尝试 MAX_RETRIES 次 = 首次 + (MAX_RETRIES-1) 次重试
    console.log(` ❌ [${model}-${EVENT_NAMES[event]}] 查询失败 (共尝试${MAX_RETRIES}次): ${error.message}`);
    return null;
  }
}

// ==================== 发送通道 ====================
// 返回 true/false 表示是否发送成功，供「送达确认」去重逻辑使用
async function sendPushPlus(content) {
  if (!PUSHPLUS_TOKEN) return false;
  try {
    // 修复：改用 HTTPS，token 不再明文传输
    const response = await axios.post('https://www.pushplus.plus/send', {
      token: PUSHPLUS_TOKEN,
      title: '火烧云预警',
      content: content,
      type: 'markdown'
    });
    // PushPlus 即使 token 无效也返回 HTTP 200，必须检查响应体 code 才算真正的送达确认
    if (response.data && response.data.code === 200) {
      console.log('✅ PushPlus 通知推送成功');
      return true;
    }
    console.log(`⚠️ PushPlus 返回异常：${JSON.stringify(response.data)}`);
    return false;
  } catch (e) {
    console.log(`⚠️ PushPlus 发送失败：${e.message}`);
    return false;
  }
}

async function sendTelegram(content) {
  if (!TG_BOT_TOKEN || !TG_CHAT_ID) return false;
  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_CHAT_ID,
      text: content,
      parse_mode: 'HTML',
      disable_web_page_preview: true
    });
    console.log('✅ Telegram 通知推送成功');
    return true;
  } catch (e) {
    console.log(`⚠️ Telegram 发送失败：${e.message}`);
    return false;
  }
}

// ==================== 主程序入口 ====================
async function main() {
  console.log('\n==================== 火烧云监控启动 ====================');
  console.log(`📍 城市：${CITY} | 🔔 阈值：${THRESHOLD} | ⏰ 时区：${TIMEZONE}`);
  console.log(`📊 模型：${MODELS.join(', ')} | 📅 事件：${EVENTS.map(e => EVENT_NAMES[e]).join(', ')}`);
  console.log(`🔔 通知窗口：${NOTIFY_WINDOW_HOURS}小时 | 📉 跌破阈值通知：${SEND_DECLINE ? '开启' : '关闭'}`);
  if (PUSHPLUS_TOKEN) console.log('📲 PushPlus 通知：已启用');
  if (TG_BOT_TOKEN && TG_CHAT_ID) console.log('✈️ Telegram 通知：已启用');

  // 修复：两个通知通道都未配置时直接退出，不浪费 API 查询
  if (!PUSHPLUS_TOKEN && !(TG_BOT_TOKEN && TG_CHAT_ID)) {
    console.log('🚫 未配置任何通知通道 (PUSHPLUS_TOKEN / TG_BOT_TOKEN+TG_CHAT_ID)，直接退出');
    process.exitCode = 1;
    return;
  }
  console.log('--------------------------------------------------------');

  const notifyResults = [];
  let anySuccess = false; // 本次运行是否有任一查询成功
  let anyFail = false;    // 本次运行是否有查询失败（用于日志与汇总判断）

  for (const model of MODELS) {
    for (const event of EVENTS) {
      const data = await querySunsetDataWithRetry(CITY, event, model);

      if (!data) {
        // 修复：查询失败与「未达标」严格区分，日志不再误导
        anyFail = true;
        console.log(` ❌ [${model}-${EVENT_NAMES[event]}] 查询失败，本次跳过该数据点`);
        if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
        continue;
      }
      anySuccess = true;

      const rawQuality = parseQuality(data.tb_quality);
      // API 偶发返回空 tb_quality（本次冒烟测试 EC 模型即出现），按 0 处理并提示
      if (!data.tb_quality || rawQuality === 0) {
        console.log(` ⚠️ [${model}-${EVENT_NAMES[event]}] tb_quality 为空或为 0，按 0 处理`);
      }
      const quality = rawQuality;
      const qInfo = getQualityInfo(quality);
      const stateKey = `${model}_${event}`;

      // 修复零值 bug：用 in 判断，上次概率恰为 0 时也能正确进入趋势判定
      const previousQuality = stateKey in state.trendState ? state.trendState[stateKey] : null;
      const trendInfo = getTrendInfo(quality, previousQuality);
      state.trendState[stateKey] = quality; // 观测值无条件记录（不管是否达标/推送）

      console.log(` ✅ 成功 -> 概率：${quality} (${qInfo.text}) ${trendInfo.symbol}${trendInfo.text} | 时间：${data.tb_event_time} | AOD: ${data.tb_aod}`);

      // 事件时间合法性检查（已过期 / 超窗口 -> 跳过推送，但观测值已记录）
      if (isEventPassed(data.tb_event_time)) {
        console.log(` ⏭️ "${EVENT_NAMES[event]}" 时间已过或超窗口 (${data.tb_event_time})，跳过推送`);
        if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
        continue;
      }

      // 修复：只在「跌破阈值」那一次推送下降（prev >= 阈值 且 cur < 阈值）
      // 普通下降（高位回落但仍在阈值上）只记日志，避免 0.7->0.5->0.3 连发
      const crossedBelow = SEND_DECLINE &&
        previousQuality !== null &&
        previousQuality >= THRESHOLD &&
        quality < THRESHOLD;

      const eventDateKey = getEventDateKey(data.tb_event_time);
      const dedupKey = `${event}:${eventDateKey}`;
      const shouldNotify = quality >= THRESHOLD || crossedBelow;

      if (!shouldNotify) {
        console.log(` ⏳ 未达标 (需 >= ${THRESHOLD})，忽略`);
        if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
        continue;
      }

      if (crossedBelow) {
        console.log(` 📉 概率跌破阈值 (${previousQuality} -> ${quality})，加入推送队列（跌破通知不受去重限制）`);
      } else if (dedupKey in state.notified) {
        // 修复：事件级去重（事件:目标日期），任一模型已推过即跳过
        console.log(` ⏭️ "${EVENT_NAMES[event]}(${eventDateKey})" 本运行周期已推送过，跳过重复预警`);
        if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
        continue;
      } else {
        console.log(` 🎯 加入推送队列 (趋势：${trendInfo.symbol}${trendInfo.text})`);
      }

      notifyResults.push({
        model, event, quality,
        tb_quality: data.tb_quality,
        tb_event_time: data.tb_event_time,
        tb_aod: data.tb_aod,
        trendInfo,
        crossedBelow,
        dedupKey
      });

      if (QUERY_DELAY > 0) await sleep(QUERY_DELAY);
    }
  }

  // 修复：标记去重必须以「至少一个通道发送成功」为前提（送达确认）
  // 推送全部失败时不写 notified，下次运行自然重试
  if (notifyResults.length > 0) {
    console.log('\n======================== 数据汇总 ========================');
    console.log(`📊 共筛选出 ${notifyResults.length} 条数据，正在推送...`);
    let delivered = false;
    if (PUSHPLUS_TOKEN) {
      delivered = (await sendPushPlus(formatForPushPlus(notifyResults, CITY, false))) || delivered;
    }
    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      delivered = (await sendTelegram(formatForTelegram(notifyResults, CITY, false))) || delivered;
    }
    if (delivered) {
      notifyResults.forEach(r => {
        // 跌破阈值的通知代表新信息，不写入去重表，允许下次运行再次提醒
        if (!r.crossedBelow) state.notified[r.dedupKey] = true;
      });
      console.log('✅ 至少一个通道发送成功，已记录去重标记');
    } else {
      console.log('⚠️ 所有通知通道均发送失败，不记录去重标记，下次运行将重试推送');
      anyFail = true; // 推送失败也让任务变红
    }
  } else if (anySuccess && !anyFail) {
    console.log('\n======================== 数据汇总 ========================');
    console.log('💤 当日无达标数据或全部超过通知窗口，不发送推送');
  } else if (!anySuccess) {
    // 修复：全部模型查询失败时，明确推送「数据不可用」而不是静默
    console.log('\n======================== 数据汇总 ========================');
    console.log('❌ 所有模型查询均失败，推送数据不可用通知');
    let delivered = false;
    if (PUSHPLUS_TOKEN) {
      delivered = (await sendPushPlus(formatForPushPlus([], CITY, true))) || delivered;
    }
    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      delivered = (await sendTelegram(formatForTelegram([], CITY, true))) || delivered;
    }
    if (!delivered) console.log('⚠️ 数据不可用通知也发送失败');
  } else {
    console.log('\n======================== 数据汇总 ========================');
    console.log('⚠️ 部分查询失败，其余无达标数据；不发送常规推送');
  }

  // 无论推送成败，观测值都已更新，落盘状态（方案 B 由 workflow 负责提交回仓库）
  saveState();

  // 部分失败也以非零退出码结束，让 Actions 任务变红，便于监控
  if (anyFail) {
    console.log('⚠️ 本次运行存在查询或推送失败，以非零退出码结束');
    process.exitCode = 1;
  }
  console.log('==================== 本次监控结束 ====================\n');
}

// 修复：失败时设置非零退出码（原脚本 catch 后永远以 0 退出，Actions 上显示绿色对勾）
main().catch(err => {
  console.error('💥 脚本异常退出：', err);
  process.exitCode = 1;
});
