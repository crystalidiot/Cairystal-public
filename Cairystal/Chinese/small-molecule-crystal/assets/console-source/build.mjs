import {build} from 'esbuild';
import {mkdir,writeFile} from 'node:fs/promises';
const out='../console';
await mkdir(out,{recursive:true});
const result=await build({entryPoints:['app.jsx'],bundle:true,minify:true,outfile:out+'/app.js',format:'iife',platform:'browser',target:['chrome115'],metafile:true,legalComments:'linked',define:{'process.env.NODE_ENV':'"production"'}});
await writeFile('build-meta.json',JSON.stringify(result.metafile,null,2));
await writeFile(out+'/index.html','<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="cairystal-token" content="__CSRF_TOKEN__"><title>Cairystal · 晶体工作台</title><link rel="stylesheet" href="/app.css"></head><body><div id="root"></div><script src="/app.js" defer></script></body></html>');
console.log('Built local console assets.');
