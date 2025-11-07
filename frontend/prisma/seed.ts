import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

async function main() {
  // Create default admin user
  const hashedPassword = await bcrypt.hash('admin123', 10)

  const adminUser = await prisma.user.upsert({
    where: { email: 'admin@army.mil' },
    update: {},
    create: {
      email: 'admin@army.mil',
      username: 'admin',
      password: hashedPassword,
      name: '관리자',
      rank: '대위',
      unit: '본부',
      role: 'admin',
      isActive: true,
    },
  })

  console.log('Created admin user:', adminUser)

  // Create test users
  const testUsers = [
    {
      email: 'user1@army.mil',
      username: 'user1',
      name: '김병장',
      rank: '병장',
      unit: '1중대',
      role: 'USER'
    },
    {
      email: 'user2@army.mil',
      username: 'user2',
      name: '이상병',
      rank: '상병',
      unit: '2중대',
      role: 'USER'
    }
  ]

  for (const userData of testUsers) {
    const hashedPw = await bcrypt.hash('password123', 10)
    const user = await prisma.user.upsert({
      where: { email: userData.email },
      update: {},
      create: {
        ...userData,
        password: hashedPw,
        isActive: true,
      },
    })
    console.log('Created user:', user.username)
  }
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })