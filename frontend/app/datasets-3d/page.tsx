'use client';

export default function Datasets3DPage() {
  return (
    <div>
      <h2>3D Datasets</h2>
      <p>3D dataset management is not yet implemented.</p>
      <p>This feature will support:</p>
      <ul>
        <li>Point cloud datasets</li>
        <li>3D mesh datasets</li>
        <li>LiDAR data</li>
        <li>3D object detection datasets</li>
      </ul>
      <div style={{ marginTop: '20px' }}>
        <button onClick={() => window.location.href = '/datasets'}>
          View 2D Datasets
        </button>
      </div>
    </div>
  );
}
