import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pnpm=process.platform==='win32'?'pnpm.cmd':'pnpm';
const python=process.env.PYTHON_BIN || 'python';
const pytestTemp=path.join(root,'.tools',`pytest-${process.pid}-${randomBytes(6).toString('hex')}`);
const compose=['compose','--project-directory',root,'--env-file',path.join(root,'.env'),'-f',path.join(root,'infra/compose/compose.yaml')];
function run(cmd,args,env=process.env,input) {
 const result=spawnSync(cmd,args,{cwd:root,env,stdio:input?['pipe','inherit','inherit']:'inherit',input,shell:process.platform==='win32'&&cmd.endsWith('.cmd')});
 if(result.error)throw result.error;if(result.status)process.exit(result.status);
}
function init() {if(!existsSync(path.join(root,'.env')))writeFileSync(path.join(root,'.env'),readFileSync(path.join(root,'.env.example'),'utf8').replaceAll('REPLACE_WITH_RANDOM_SECRET',randomBytes(32).toString('hex')).replaceAll('REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS',randomBytes(32).toString('hex')),{mode:0o600});}
function setting(name,fallback) {const match=readFileSync(path.join(root,'.env'),'utf8').match(new RegExp(`^${name}=(.*)$`,'m'));return match?match[1].trim().replace(/^(['"])(.*)\1$/,'$2'):fallback;}
const [action,...args]=process.argv.slice(2);
if(action==='stack'){init();run('docker',[...compose,...args]);}
else if(action==='quick') {
 run(pnpm,['lint']);run(pnpm,['typecheck']);
 run(python,['-m','ruff','check','apps/api','scripts','tests/tooling']);
 run(python,['-m','pytest','-c','apps/api/pyproject.toml','apps/api/tests','tests/tooling','-m',process.env.TEST_DATABASE_URL?'not compose and not ssh':'not integration and not compose and not ssh','--basetemp',pytestTemp,'-q']);
 run(pnpm,['build']);
} else if(action==='full') {
  init();
  const env={...process.env,RATE_LIMIT:'1000',PROXY_RATE:'600r/m',PROXY_BURST:'100',ADMIN_LOGIN_LIMIT:'100',ADMIN_PROXY_RATE:'600r/m',ADMIN_PROXY_BURST:'100',E2E_BASE_URL:'http://localhost:8080',E2E_COMPOSE:'true',E2E_ADMIN_PASSWORD:randomBytes(24).toString('hex')};
 run(pnpm,['lint'],env);run(pnpm,['typecheck'],env);run(python,['-m','ruff','check','apps/api','scripts','tests/tooling'],env);
  run('docker',[...compose,'up','--build','-d','--wait','--wait-timeout','180'],env);
 const dbUser=setting('POSTGRES_USER','lab');
 run('docker',[...compose,'exec','-T','db','psql','-U',dbUser,'-d','postgres','-c','DROP DATABASE IF EXISTS lab_test WITH (FORCE)'],env);
 run('docker',[...compose,'exec','-T','db','createdb','-U',dbUser,'lab_test'],env);
 const testCompose=[...compose,'-f',path.join(root,'infra/compose/test.yaml')];
 run('docker',[...testCompose,'build','api-test'],env);
 run('docker',[...testCompose,'run','--rm','api-test'],env);
 run('docker',[...compose,'exec','-T','api','python','-c',"import sys; from sqlalchemy import create_engine; from app.config import Settings; from app.admin_auth import manage; e=create_engine(Settings.from_env().database_url); p=sys.stdin.read(); names=[x['username'] for x in manage(e,'list')]; [(manage(e,'reset-password' if n in names else 'create',n,p)) for n in ['synthetic_admin_one','synthetic_admin_two','synthetic_admin_three']]"],env,env.E2E_ADMIN_PASSWORD);
 run(pnpm,['test:e2e'],env);
 for(const module of ['compose','https','deploy-failures'])run(python,['-m','scripts.verify.'+module],env);
 run(python,['-m','pytest','-c','apps/api/pyproject.toml','tests/tooling','--basetemp',pytestTemp,'-q'],env);
} else throw Error('Use stack, quick or full');
