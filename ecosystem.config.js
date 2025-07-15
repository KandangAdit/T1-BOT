module.exports = {
  apps: [
    {
      name: 'T1-BOT',
      script: 'bot.py',
      interpreter: '.venv/bin/python3',
      cwd: __dirname,
      max_memory_restart: '50M',
      watch: false,
      out_file: '.logs/out.log',
      error_file: '.logs/error.log',
    },
  ],
};
