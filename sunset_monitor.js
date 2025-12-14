/*
青龙火烧云概率监控脚本 v2.19
功能：监控日出日落火烧云概率，当概率高于阈值时发送Bark通知
作者：Claude
更新时间：2025-12-13
*/

const axios = require('axios');

// ==================== 配置区 ====================
// 必填配置
const CITY = process.env.SUNSET_CITY || '广东省-深圳'; // 查询城市
const BARK_URL = process.env.BARK_URL || ''; // Bark推送地址，格式：https://api.day.app/你的KEY

// 可选配置
const THRESHOLD = parseFloat(process.env.SUNSET_THRESHOLD || '0.5'); // 火烧云概率阈值
const MODELS = process.env.SUNSET_MODELS ? process.env.SUNSET_MODELS.split(',') : ['EC', 'GFS']; // 模型选择
const EVENTS = ['set_2', 'set_1', 'rise_2']; // 监控事件：明天落日、今天落日、明天日出

// ==================== 全局变量 ====================
const API_BASE = 'https://sunsetbot.top/';
const EVENT_NAMES = {
  'set_1': '今天落日',
  'set_2': '明天落日',
  'rise_1': '明天日出',
  'rise_2': '后天日出'
};

// 用于记录今天落日是否已发送通知（防止重复推送）
let todaySunsetNotified = false;

// ==================== 工具函数 ====================

/**
 * 生成7位随机数字作为query_id
 */
function generateQueryId() {
  return Math.floor(1000000 + Math.random() * 9000000).toString();
}

/**
 * 解析tb_quality值（提取数字部分）
 */
function parseQuality(qualityStr) {
  if (!qualityStr) return 0;
  const match = qualityStr.match(/[\d.]+/);
  return match ? parseFloat(match[0]) : 0;
}

/**
 * 获取质量等级描述
 */
function getQualityLevel(quality) {
  if (quality >= 0.8) return '🔥 极佳';
  if (quality >= 0.6) return '✨ 很好';
  if (quality >= 0.4) return '☀️ 一般';
  if (quality >= 0.2) return '🌤️ 较差';
  return '❌ 不烧';
}

/**
 * 查询火烧云数据
 */
async function querySunsetData(city, event, model) {
  const queryId = generateQueryId();
  const encodedCity = encodeURIComponent(city);
  
  const url = `${API_BASE}?query_id=${queryId}&intend=select_city&query_city=${encodedCity}&event_date=None&event=${event}&times=None&model=${model}`;
  
  try {
    const response = await axios.get(url, {
      headers: {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'referer': 'https://sunsetbot.top/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
      },
      timeout: 10000
    });
    
    if (response.data && response.data.status === 'ok') {
      return response.data;
    }
    return null;
  } catch (error) {
    console.log(`❌ 查询失败 [${model}-${event}]: ${error.message}`);
    return null;
  }
}

/**
 * 发送Bark通知
 */
async function sendBarkNotification(title, content, group = '火烧云预报') {
  if (!BARK_URL) {
    console.log('⚠️ 未配置BARK_URL，跳过推送');
    return false;
  }
  
  try {
    const url = `${BARK_URL}/${encodeURIComponent(title)}/${encodeURIComponent(content)}?group=${encodeURIComponent(group)}&sound=bell`;
    const response = await axios.get(url, { timeout: 5000 });
    
    if (response.data && response.data.code === 200) {
      console.log('✅ Bark通知发送成功');
      return true;
    }
    console.log('⚠️ Bark通知发送失败:', response.data);
    return false;
  } catch (error) {
    console.log(`❌ Bark推送异常: ${error.message}`);
    return false;
  }
}

/**
 * 格式化通知内容（合并多模型对比）
 */
function formatNotification(results) {
  const lines = [];
  const eventGroups = {};
  
  // 按事件分组
  results.forEach(r => {
    if (!eventGroups[r.event]) {
      eventGroups[r.event] = [];
    }
    eventGroups[r.event].push(r);
  });
  
  // 生成通知内容
  Object.keys(eventGroups).forEach(event => {
    const eventData = eventGroups[event];
    const eventName = EVENT_NAMES[event] || event;
    
    lines.push(`\n【${eventName}】`);
    
    eventData.forEach(data => {
      const quality = parseQuality(data.tb_quality);
      const level = getQualityLevel(quality);
      const time = data.tb_event_time || '未知';
      const aod = data.tb_aod || '未知';
      
      lines.push(`${data.model}: ${level} (${quality})`);
      lines.push(`时间: ${time}`);
      lines.push(`AOD: ${aod}`);
      lines.push('');
    });
  });
  
  return lines.join('\n');
}

/**
 * 主函数
 */
async function main() {
  console.log('==================== 火烧云监控开始 ====================');
  console.log(`📍 监控城市: ${CITY}`);
  console.log(`📊 阈值设置: ${THRESHOLD}`);
  console.log(`🔬 监控模型: ${MODELS.join(', ')}`);
  console.log(`🎯 监控事件: ${EVENTS.map(e => EVENT_NAMES[e]).join(', ')}`);
  console.log('========================================================\n');
  
  const allResults = [];
  const notifyResults = []; // 需要通知的结果
  
  // 遍历所有模型和事件
  for (const model of MODELS) {
    for (const event of EVENTS) {
      console.log(`🔍 正在查询: ${model} - ${EVENT_NAMES[event]}...`);
      
      const data = await querySunsetData(CITY, event, model);
      
      if (data) {
        const quality = parseQuality(data.tb_quality);
        const result = {
          model,
          event,
          eventName: EVENT_NAMES[event],
          quality,
          rawQuality: data.tb_quality,
          time: data.tb_event_time,
          aod: data.tb_aod,
          data
        };
        
        allResults.push(result);
        
        console.log(`   质量: ${data.tb_quality} | AOD: ${data.tb_aod}`);
        console.log(`   时间: ${data.tb_event_time}`);
        
        // 判断是否需要通知
        if (quality >= THRESHOLD) {
          // 今天落日(set_1)已通知过则跳过
          if (event === 'set_1' && todaySunsetNotified) {
            console.log(`   ⏭️ 今天落日已通知过，跳过`);
          } else {
            notifyResults.push(result);
            console.log(`   ✨ 达到阈值，将发送通知`);
            
            // 标记今天落日已通知
            if (event === 'set_1') {
              todaySunsetNotified = true;
            }
          }
        }
      } else {
        console.log(`   ❌ 查询失败`);
      }
      
      // 延迟避免请求过快
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  
  console.log('\n==================== 查询完成 ====================');
  console.log(`📊 共查询 ${allResults.length} 条数据`);
  console.log(`🔔 需要通知 ${notifyResults.length} 条数据\n`);
  
  // 发送通知
  if (notifyResults.length > 0) {
    const title = `🌅 ${CITY} 火烧云预警`;
    const content = formatNotification(notifyResults);
    
    console.log('📱 准备发送通知...');
    console.log(content);
    
    await sendBarkNotification(title, content);
  } else {
    console.log('💤 暂无达到阈值的数据，无需通知');
  }
  
  console.log('\n==================== 执行结束 ====================');
}

// 执行主函数
main().catch(error => {
  console.error('❌ 脚本执行出错:', error);
  process.exit(1);
});
