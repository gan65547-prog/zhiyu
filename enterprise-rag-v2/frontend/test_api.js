#!/usr/bin/env node
// 测试前端API调用

import axios from 'axios';

const testEmail = process.env.GANFY_TEST_EMAIL;
const testPassword = process.env.GANFY_TEST_PASSWORD;
if (!testEmail || !testPassword) {
  throw new Error('Set GANFY_TEST_EMAIL and GANFY_TEST_PASSWORD before running this script.');
}

async function testFrontendApi() {
  try {
    // 1. 登录获取token
    const loginResponse = await axios.post('http://localhost:8000/api/v1/auth/login', {
      email: testEmail,
      password: testPassword
    });
    
    console.log('Login successful:', loginResponse.status);
    const token = loginResponse.data.data.access_token;
    
    // 2. 测试文档分段API
    const documentId = '59e526e6-56c1-42e6-bd29-a2ed81a7d018';
    const segmentsResponse = await axios.get(
      `http://localhost:8000/api/v1/documents/${documentId}/segments`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Origin': 'http://localhost:3000'
        }
      }
    );
    
    console.log('Segments API successful:', segmentsResponse.status);
    console.log('Segments count:', segmentsResponse.data.data.items.length);
    console.log('Total segments:', segmentsResponse.data.data.total);
    
    // 3. 测试其他API
    const datasetsResponse = await axios.get(
      'http://localhost:8000/api/v1/datasets',
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    
    console.log('Datasets API successful:', datasetsResponse.status);
    console.log('Datasets count:', datasetsResponse.data.data.items.length);
    
    console.log('\n✅ All tests passed!');
  } catch (error) {
    console.error('❌ Test failed:', error.response?.status, error.response?.data);
  }
}

testFrontendApi();
