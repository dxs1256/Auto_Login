/*
青龙火烧云概率监控脚本 (多通道通知版) v2.21
功能：监控日出日落火烧云概率，支持企业微信机器人和Telegram通知
作者：Claude
更新时间：2025-12-14
*/

const axios = require('axios');

// ==================== 配置区 ====================
// 基础配置
const CITY = process.env.SUNSET_CITY || '广东省-深圳'; 
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5'); 
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS']; 
const EVENTS = ['set_2', 'set_1', 'rise_2']; 

// 通道配置 (为空则不发送)
const WX_WEBHOOK_URL = process.env.WX_WEBHOOK_URL || ''; // 企业微信
const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || '';     // Telegram Bot Token
const TG_CHAT_ID = process.env.TG_CHAT_ID || '';         // Telegram Chat ID

// ==================== 全局变量 ====================
const API_BASE = 'https://sunsetbot.top/';
const EVENT_NAMES = {
  'set_1': '今天落日',
  'set_2': '明天落日',
  'rise_1': '明天日出',
  'rise_2': '后天日出'
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

function getQualityLevel(quality) {
  if (quality >= 0.8) return '🔥 极佳';
  if (quality >= 0.6) return '✨ 很好';
  if (quality >= 0.4) return '☀️ 一般';
  if (quality >= 0.2) return '🌤️ 较差';
  return '❌ 不烧';
}

// -------------------- 数据查询 --------------------

async function querySunsetData(city, event, model) {
  const queryId = generateQueryId();
  const encodedCity = encodeURIComponent(city);
  const url = `${API_BASE}?query_id=${queryId}&intend=select_city&query_city=${encodedCity}&event_date=None&event=${event}&times=None&model=${model}`;
  
  try {
    const response = await axios.get(url, {
      headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
      },
      timeout: 10000
    });
    if (response.data && response.data.status === 'ok') return response.data;
    return null;
  } catch (error) {
    console.log(`❌ 查询失败 [${model}-${event}]: ${error.message}`);
    return null;
  }
}

// -------------------- 格式化与发送逻辑 --------------------

/**
 * 格式化：企业微信 (Markdown + 颜色)
 */
function formatForWeCom(results, city) {
  const lines = [`## 🌅 ${city} 火烧云预警`];
  const eventGroups = groupByEvent(results);
  
  Object.keys(eventGroups).forEach(event => {
    lines.push(`\n### ${EVENT_NAMES[event] || event}`);
    eventGroups[event].forEach(data => {
      const levelText = getQualityLevel(data.quality);
      // 企微颜色代码: warning(橙红), info(绿), comment(灰)
      let color = 'comment';
      if (data.quality >= 0.6) color = 'warning';
      else if (data.quality >= 0.4) color = 'info';
      
      lines.push(`> **${data.model}**: <font color="${color}">${levelText}</font> (${data.quality})`);
      lines.push(`> <font color="comment">时间: ${data.tb_event_time}</font>`);
      lines.push('>'); 
    });
  });
  return lines.join('\n');
}

/**
 * 格式化：Telegram (HTML)
 * Telegram 不支持 colored text，只能用 Emoji 和 Bold
 */
function formatForTelegram(results, city) {
  const lines = [`<b>🌅 ${city} 火烧云预警</b>`];
  const eventGroups = groupByEvent(results);

  Object.keys(eventGroups).forEach(event => {
    lines.push(``); // 空行
    lines.push(`<u><b>${EVENT_NAMES[event] || event}</b></u>`);
    eventGroups[event].forEach(data => {
      lines.push(`<b>${data.model}</b>: ${getQualityLevel(data.quality)} <code>(${data.quality})</code>`);
      lines.push(`时间: ${data.tb_event_time}`);
      lines.push(`AOD: ${data.tb_aod}`);
    });
  });
  return lines.join('\n');
}

function groupByEvent(results) {
  const groups = {};
  results.forEach(r => {
    if (!groups[r.event]) groups[r.event] = [];
    groups[r.event].push(r);
  });
  return groups;
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
      parse_mode: 'HTML', // 使用 HTML 模式以支持加粗
      disable_web_page_preview: true
    });
    console.log('✅ Telegram 通知已发送');
  } catch (e) {
    console.log(`⚠️ Telegram 发送失败: ${e.message}`);
  }
}

// -------------------- 主程序 --------------------

async function main() {
  console.log('==================== 火烧云监控启动 ====================');
  console.log(`📍 城市: ${CITY} | 阈值: ${THRESHOLD}`);
  if(WX_WEBHOOK_URL) console.log('🔔 企业微信通知: 已启用');
  if(TG_BOT_TOKEN) console.log('✈️ Telegram通知: 已启用');
  
  const notifyResults = [];
  
  for (const model of MODELS) {
    for (const event of EVENTS) {
      console.log(`🔍 查询: ${model} - ${EVENT_NAMES[event]}...`);
      const data = await querySunsetData(CITY, event, model);
      
      if (data) {
        const quality = parseQuality(data.tb_quality);
        console.log(`   --> ${data.tb_quality} | ${data.tb_event_time}`);
        
        if (quality >= THRESHOLD) {
          if (event === 'set_1' && todaySunsetNotified) {
            console.log(`   ⏭️ 今天落日已通知，跳过`);
          } else {
            notifyResults.push({
              model, event, quality,
              tb_quality: data.tb_quality,
              tb_event_time: data.tb_event_time,
              tb_aod: data.tb_aod
            });
            if (event === 'set_1') todaySunsetNotified = true;
          }
        }
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  
  if (notifyResults.length > 0) {
    console.log('\n📱 正在推送通知...');
    
    // 1. 发送企业微信
    if (WX_WEBHOOK_URL) {
      const wxContent = formatForWeCom(notifyResults, CITY);
      await sendWeChat(wxContent);
    }
    
    // 2. 发送 Telegram
    if (TG_BOT_TOKEN && TG_CHAT_ID) {
      const tgContent = formatForTelegram(notifyResults, CITY);
      await sendTelegram(tgContent);
    }
    
  } else {
    console.log('\n💤 无高概率数据，不发送通知');
  }
}

main().catch(console.error);
