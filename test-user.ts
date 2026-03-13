import { PrismaClient } from '@prisma/client';
import { verifyPassword } from './lib/security/password';

const prisma = new PrismaClient();

async function test() {
    try {
        const user = await prisma.user.findUnique({
            where: { email: 'clinician@carepulse.dev' },
        });

        console.log('User found:', user);

        if (user) {
            const isValid = await verifyPassword('ChangeThisNow123!', user.passwordHash);
            console.log('Password verification result:', isValid);
        }
    } catch (error) {
        console.error('Error:', error);
    } finally {
        await prisma.$disconnect();
    }
}

test();
