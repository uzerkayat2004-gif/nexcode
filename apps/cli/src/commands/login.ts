import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import open from 'open';
import { saveAuth, generateDeviceCode, pollForAuth } from '../utils/auth.js';

export const loginCommand = new Command('login')
  .description('Sign in to NexCode')
  .option('--api-key <key>', 'Authenticate with an API key')
  .action(async (options) => {
    if (options.apiKey) {
      await loginWithApiKey(options.apiKey);
    } else {
      await loginWithBrowser();
    }
  });

async function loginWithApiKey(apiKey: string) {
  if (!apiKey.startsWith('nxc_sk_')) {
    console.error(chalk.red('Error: Invalid API key format. API keys must start with nxc_sk_'));
    process.exit(1);
  }

  const spinner = ora('Validating API key...').start();

  try {
    // TODO: Validate API key with backend
    await saveAuth({
      type: 'api-key',
      apiKey,
      email: 'apikey@nexcode.app',
    });

    spinner.succeed(chalk.green('Authenticated with API key'));
    console.log(chalk.gray('You can now use NexCode CLI commands.'));
  } catch (error) {
    spinner.fail(chalk.red('Failed to validate API key'));
    process.exit(1);
  }
}

async function loginWithBrowser() {
  const deviceCode = generateDeviceCode();
  const authUrl = `http://localhost:3000/auth/login?device=${deviceCode}`;

  console.log(chalk.cyan('Opening browser for authentication...'));
  console.log(chalk.gray(`If the browser doesn't open, visit: ${authUrl}`));
  console.log('');

  try {
    await open(authUrl);
  } catch {
    console.log(chalk.yellow('Could not open browser automatically.'));
  }

  const spinner = ora('Waiting for authentication...').start();

  try {
    const auth = await pollForAuth(deviceCode);
    await saveAuth(auth);

    spinner.succeed(chalk.green(`Authenticated as ${auth.email}`));
    console.log(chalk.gray('Session saved to ~/.nexcode/auth.json'));
  } catch (error) {
    spinner.fail(chalk.red('Authentication timed out'));
    process.exit(1);
  }
}
