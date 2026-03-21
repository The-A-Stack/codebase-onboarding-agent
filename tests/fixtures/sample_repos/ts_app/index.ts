import express, { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { validateUser } from './validators';
import * as authUtils from './lib/auth';

const app = express();
const prisma = new PrismaClient();

const PORT = process.env.PORT || 3000;
const DATABASE_URL = process.env.DATABASE_URL;
const JWT_SECRET = process.env['JWT_SECRET'];

app.get('/api/users', async (req: Request, res: Response): Promise<void> => {
  const users = await prisma.user.findMany();
  res.json(users);
});

app.post('/api/users', async (req: Request, res: Response): Promise<void> => {
  const validated = validateUser(req.body);
  const user = await prisma.user.create({ data: validated });
  res.status(201).json(user);
});

export async function startServer(): Promise<void> {
  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
}

export const healthCheck = (): string => {
  return 'ok';
};
