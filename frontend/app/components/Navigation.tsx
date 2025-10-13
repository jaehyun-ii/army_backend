'use client';

import { useAuth } from '@/lib/auth';

export default function Navigation() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <header>
      <h1>🎯 Adversarial Vision Platform</h1>
      <nav>
        <ul>
          <li><a href="/">🏠 Dashboard</a></li>
          <li>
            <span>📊 Datasets</span>
            <ul>
              <li><a href="/datasets">2D Datasets</a></li>
              <li><a href="/datasets-3d">3D Datasets</a></li>
              <li><a href="/datasets/upload">Upload Dataset</a></li>
            </ul>
          </li>
          <li>
            <span>🤖 Models</span>
            <ul>
              <li><a href="/models">Model Repository</a></li>
              <li><a href="/models/upload">Upload Model</a></li>
            </ul>
          </li>
          <li>
            <span>⚔️ Attacks</span>
            <ul>
              <li><a href="/attacks/adversarial-patch/create">Create Adversarial Patch</a></li>
              <li><a href="/attacks/noise-attack/create">Create Noise Attack</a></li>
            </ul>
          </li>
          <li>
            <span>📋 Attack Results</span>
            <ul>
              <li><a href="/attacks/adversarial-patch/patches">Generated Patches</a></li>
              <li><a href="/attacks/adversarial-patch/attack-datasets">Patch Attack Datasets</a></li>
              <li><a href="/attacks/noise-attack/results">Noise Attack Datasets</a></li>
            </ul>
          </li>
          <li>
            <span>📈 Evaluation</span>
            <ul>
              <li><a href="/evaluation/create">Run Evaluation</a></li>
              <li><a href="/evaluation/history">Evaluation History</a></li>
              <li><a href="/evaluation/compare">Compare Results</a></li>
            </ul>
          </li>
          <li>
            <span>📹 Real-time</span>
            <ul>
              <li><a href="/realtime/cameras">Cameras</a></li>
              <li><a href="/realtime/sessions/create">Live Sessions</a></li>
            </ul>
          </li>
          <li>
            <span>🧪 Experiments</span>
            <ul>
              <li><a href="/experiments">Experiment List</a></li>
              <li><a href="/experiments/create">Create Experiment</a></li>
            </ul>
          </li>
          <li>
            {isAuthenticated ? (
              <>
                <button onClick={logout}>로그아웃</button>
              </>
            ) : (
              <>
                <a href="/auth/login">로그인</a>
                {' | '}
                <a href="/auth/register">회원가입</a>
              </>
            )}
          </li>
        </ul>
      </nav>
    </header>
  );
}
