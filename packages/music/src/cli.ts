import { parseSource } from './parser.js';
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => { input += chunk; if (input.length > 2_000_000) process.exit(1); });
process.stdin.on('end', () => {
  try {
    const request: unknown = JSON.parse(input);
    if (!request || typeof request !== 'object' || !('op' in request) || request.op !== 'parse' || !('source' in request) || typeof request.source !== 'string') throw new Error('Invalid request');
    process.stdout.write(JSON.stringify({document:parseSource(request.source)}));
  } catch { process.stdout.write(JSON.stringify({error:'Invalid request'})); process.exitCode = 1; }
});
