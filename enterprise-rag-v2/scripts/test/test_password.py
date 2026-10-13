import bcrypt

# 测试密码加密和验证
def test_password():
    password = "SuperAdmin123!@#"
    
    # 加密密码
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"原始密码: {password}")
    print(f"加密后: {hashed}")
    
    # 验证密码
    is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    print(f"验证结果: {is_valid}")

if __name__ == "__main__":
    test_password()