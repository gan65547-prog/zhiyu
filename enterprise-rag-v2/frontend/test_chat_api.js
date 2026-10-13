#!/usr/bin/env node
// 测试聊天相关API

import axios from 'axios';

const testEmail = process.env.GANFY_TEST_EMAIL;
const testPassword = process.env.GANFY_TEST_PASSWORD;
if (!testEmail || !testPassword) {
  throw new Error('Set GANFY_TEST_EMAIL and GANFY_TEST_PASSWORD before running this script.');
}

async function testChatApi() {
  try {
    // 1. 登录获取token
    const loginResponse = await axios.post('http://localhost:8000/api/v1/auth/login', {
      email: testEmail,
      password: testPassword
    });
    
    console.log('Login successful:', loginResponse.status);
    const token = loginResponse.data.data.access_token;
    
    // 2. 测试获取会话列表
    const conversationsResponse = await axios.get('http://localhost:8000/api/v1/chat/conversations', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    console.log('Conversations successful:', conversationsResponse.status);
    console.log('Conversations count:', conversationsResponse.data.data.length);
    
    // 3. 测试获取数据集列表（用于聊天）
    const datasetsResponse = await axios.get('http://localhost:8000/api/v1/datasets/', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    console.log('Datasets successful:', datasetsResponse.status);
    const datasets = datasetsResponse.data.data.items;
    
    if (datasets.length) {
      const datasetId = datasets[0].id;
      console.log('Using dataset:', datasetId);
      
      // 4. 测试发送聊天请求
      const chatResponse = await axios.post('http://localhost:8000/api/v1/chat', {
        dataset_id: datasetId,
        query: '你好，测试聊天功能',
        retrieval_mode: 'semantic',
        top_k: 3,
        temperature: 0.7,
        max_tokens: 500
      }, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      console.log('Chat successful:', chatResponse.status);
      console.log('Chat response:', chatResponse.data.data.answer);
    }
    
    console.log('\n✅ All tests passed!');
  } catch (error) {
    console.error('❌ Test failed:', error.response?.status, error.response?.data);
  }
}

testChatApi();
