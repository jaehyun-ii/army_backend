export default function Home() {
  return (
    <div>
      <h2>Dashboard</h2>
      <p>Welcome to Adversarial Vision Platform</p>

      <section>
        <h3>Quick Links</h3>
        <ul>
          <li><a href="/attacks/adversarial-patch/create">Create Adversarial Patch</a></li>
          <li><a href="/attacks/noise-attack/create">Create Noise Attack</a></li>
          <li><a href="/evaluation/create">Run Model Evaluation</a></li>
          <li><a href="/realtime/sessions/create">Start Live Detection</a></li>
          <li><a href="/experiments/create">Create New Experiment</a></li>
        </ul>
      </section>

      <section>
        <h3>Recent Activities</h3>
        <p>No recent activities</p>
      </section>
    </div>
  )
}
