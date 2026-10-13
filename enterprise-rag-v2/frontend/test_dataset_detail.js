#!/usr/bin/env node
// 测试前端数据集详情API调用

import axios from 'axios';

const testEmail = process.env.GANFY_TEST_EMAIL;
const testPassword = process.env.GANFY_TEST_PASSWORD;
if (!testEmail || !testPassword) {
  throw new Error('Set GANFY_TEST_EMAIL and GANFY_TEST_PASSWORD before running this script.');
}

async function testDatasetDetail() {
  try {
    // 1. 登录获取token
    const loginResponse = await axios.post('http://localhost:8000/api/v1/auth/login', {
      email: testEmail,
      password: testPassword
    });
    
    console.log('Login successful:', loginResponse.status);
    const token = loginResponse.data.data.access_token;
    
    // 2. 获取数据集列表
    const datasetsResponse = await axios.get('http://localhost:8000/api/v1/datasets/', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    console.log('Datasets successful:', datasetsResponse.status);
    const datasets = datasetsResponse.data.data.items;
    
    if (!datasets.length) {
      console.log('No datasets found');
      return;
    }
    
    // 3. 获取第一个数据集详情
    const datasetId = datasets[0].id;
    const detailResponse = await axios.get(`http://localhost:8000/api/v1/datasets/${datasetId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    console.log('Dataset detail successful:', detailResponse.status);
    const dataset = detailResponse.data.data;
    
    console.log('\nDataset info:');
    console.log('Name:', dataset.name);
    console.log('Document count:', dataset.document_count);
    console.log('Statistics:', dataset.statistics);
    
    console.log('\n✅ All tests passed!');
  } catch (error) {
    console.error('❌ Test failed:', error.response?.status, error.response?.data);
  }
}

testDatasetDetail();
