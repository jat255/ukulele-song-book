import {defineConfig} from 'vite';
const target=process.env.SONGBOOK_API_TARGET ?? 'http://127.0.0.1:8000';
export default defineConfig({server:{host:'127.0.0.1',strictPort:true,proxy:{'/api':target,'/health':target}}});
