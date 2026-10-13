export const validateEmail = (email: string) => {
  // 更宽松的邮箱验证，只检查基本格式
  if (!email || typeof email !== 'string') return false
  email = email.trim()
  const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
  return re.test(email)
}

export const validatePassword = (password: string) => {
  return password.length >= 8
}

export const validatePasswordStrength = (password: string) => {
  if (password.length < 8) {
    return { valid: false, message: '密码长度至少8位' }
  }
  return { valid: true, message: '' }
}

export const validateRequired = (value: any) => {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }
  return value !== null && value !== undefined
}
