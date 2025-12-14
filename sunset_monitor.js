/*
青龙火烧云概率监控脚本 (企业微信版) v2.20
功能：监控日出日落火烧云概率，当概率高于阈值时发送企业微信机器人通知
作者：Claude
更新时间：2025-12-14
*/

const axios = require('axios');

// ==================== 配置区 ====================
// 必填配置
const CITY = process.env.SUNSET_CITY || '广东省-深圳'; // 查询城市
// 企业微信机器人的 Webhook 地址 (格式: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx)
const WX_WEBHOOK_URL = process.env.WX_WEBHOOK_URL || ''; 

// 可选配置
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5'); // 火烧云概率阈值
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS']; // 模型选择
const EVENTS = ['set_2', 'set_1', 'rise_2']; // 监控事件

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

/**
 * 获取带颜色的质量描述 (企业微信 Markdown 格式)
 */
function getColoredQualityLevel(quality) {
  const levelText = getQualityLevel(quality);
  // 绿色: info, 橙红色: warning, 灰色: comment
  if (quality >= 0.6) return `<font color="warning">${levelText}</font>`;
  if (quality >= 0.4) return `<font color="info">${levelText}</font>`;
  return `<font color="comment">${levelText}</font>`;
}

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

/**
 * 发送企业微信机器人通知 (Markdown)
 */
async function sendWeChatNotification(title, content) {
  if (!WX_WEBHOOK_URL) {
    console.log('⚠️ 未配置 WX_WEBHOOK_URL，跳过推送');
    return false;
  }

  // 组装 Markdown 内容
  const markdownContent = `## ${title}\n${content}`;

  try {
    const response = await axios.post(WX_WEBHOOK_URL, {
      msgtype: "markdown",
      markdown: {
        content: markdownContent
      }
    });

    if (response.data && response.data.errcode === 0) {
      console.log('✅ 企业微信通知发送成功');
      return true;
    }
    console.log('⚠️ 企业微信发送失败:', response.data);
    return false;
  } catch (error) {
    console.log(`❌ 推送异常: ${error.message}`);
    return false;
  }
}

/**
 * 格式化为 Markdown 字符串
 */
function formatNotification(results) {
  const lines = [];
  const eventGroups = {};
  
  results.forEach(r => {
    if (!eventGroups[r.event]) eventGroups[r.event] = [];
    eventGroups[r.event].push(r);
  });
  
  Object.keys(eventGroups).forEach(event => {
    const eventData = eventGroups[event];
    const eventName = EVENT_NAMES[event] || event;
    
    // 使用引用格式 > 区分不同事件
    lines.push(`\n### ${eventName}`);
    
    eventData.forEach(data => {
      const quality = parseQuality(data.tb_quality);
      const levelHtml = getColoredQualityLevel(quality);
      const time = data.tb_event_time || '未知';
      const aod = data.tb_aod || '未知';
      
      // 每一行详情
      lines.push(`> **${data.model}**: ${levelHtml} (${quality})`);
      lines.push(`> <font color="comment">时间: ${time}</font>`);
      lines.push(`> <font color="comment">AOD: ${aod}</font>`);
      lines.push('>'); // 空行间隔
    });
  });
  
  return lines.join('\n');
}

/**
 * 主函数
 */
async function main() {
  console.log('==================== 火烧云监控开始 (WeChat版) ====================');
  console.log(`📍 监控城市: ${CITY}`);
  
  const notifyResults = [];
  
  for (const model of MODELS) {
    for (const event of EVENTS) {
      console.log(`🔍 查询: ${model} - ${EVENT_NAMES[event]}...`);
      const data = await querySunsetData(CITY, event, model);
      
      if (data) {
        const quality = parseQuality(data.tb_quality);
        const result = {
          model, event, eventName: EVENT_NAMES[event],
          quality, tb_quality: data.tb_quality,
          tb_event_time: data.tb_event_time, tb_aod: data.tb_aod
        };
        
        console.log(`   质量: ${data.tb_quality} | 时间: ${data.tb_event_time}`);
        
        if (quality >= THRESHOLD) {
          if (event === 'set_1' && todaySunsetNotified) {
            console.log(`   ⏭️ 今天落日已通知过`);
          } else {
            notifyResults.push(result);
            if (event === 'set_1') todaySunsetNotified = true;
          }
        }
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  
  if (notifyResults.length > 0) {
    const title = `🌅 ${CITY} 火烧云预警`;
    const content = formatNotification(notifyResults);
    console.log('📱 发送企业微信通知...');
    await sendWeChatNotification(title, content);
  } else {
    console.log('💤 暂无高概率数据，无需通知');
  }
}

main().catch(console.error);
