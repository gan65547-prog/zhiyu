// 测试前端API调用格式

import axios from 'axios';

const testEmail = process.env.GANFY_TEST_EMAIL;
const testPassword = process.env.GANFY_TEST_PASSWORD;
if (!testEmail || !testPassword) {
  throw new Error('Set GANFY_TEST_EMAIL and GANFY_TEST_PASSWORD before running this script.');
}

async function testFrontendCreateDataset() {
  // 模拟前端登录
  const loginResponse = await axios.post('http://localhost:8000/api/v1/auth/login', {
    email: testEmail,
    password: testPassword
  });
  
  console.log('Login status:', loginResponse.status);
  const token = loginResponse.data.data.access_token;
  
  // 模拟前端创建数据集的请求格式
  const frontendData = {
    name: '前端测试数据集',
    description: '测试前端API调用',
    config: {
      embedding_model: 'bge-small-zh-v1.5',
      retrieval_model: 'semantic',
      chunk_size: 500,
      chunk_overlap: 50
    }
  };
  
  // 转换为后端格式
  const backendData = {
    name: frontendData.name,
    description: frontendData.description,
    embedding_model: frontendData.config?.embedding_model || 'bge-small-zh-v1.5',
    chunk_size: frontendData.config?.chunk_size || 500,
    chunk_overlap: frontendData.config?.chunk_overlap || 50
  };
  
  console.log('\nFrontend data:', frontendData);
  console.log('Backend data:', backendData);
  
  // 调用API
  const response = await axios.post('http://localhost:8000/api/v1/datasets/', backendData, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  console.log('\nCreate dataset status:', response.status);
  console.log('Create dataset response:', response.data);
}

testFrontendCreateDataset()
  .then(() => console.log('\n✅ 测试成功！'))
  .catch((error) => {
    console.error('\n❌ 测试失败:', error.response?.data || error.message);
  });
