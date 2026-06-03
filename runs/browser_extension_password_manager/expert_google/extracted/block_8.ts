import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import { Pool } from 'pg';
import { login, register, getSalt } from './controllers/auth.controller';
import { syncVault } from './controllers/vault.controller';
import { auditLogger } from './middleware/audit.middleware';

const app = express();
const port = process.env.PORT || 3000;

export const db = new Pool({
  connectionString: process.env.DATABASE_URL
});

// Security Hardening Middlewares
app.use(helmet());
app.use(cors({ origin: 'chrome-extension://*' })); // Restrict to extension origin
app.use(express.json());
app.use(auditLogger);

// Routes
app.get('/api/auth/salt', getSalt);
app.post('/api/auth/register', register);
app.post('/api/auth/login', login);
app.post('/api/vault/sync', syncVault);

app.listen(port, () => {
  console.log(`SecureVault API running on port ${port}`);
});
