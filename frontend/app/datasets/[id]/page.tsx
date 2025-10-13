'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';

export default function DatasetDetailPage() {
  const params = useParams();
  const datasetId = params.id as string;

  const [dataset, setDataset] = useState<any>(null);
  const [images, setImages] = useState<any[]>([]);
  const [metadata, setMetadata] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'images' | 'metadata'>('images');
  const [selectedImage, setSelectedImage] = useState<any>(null);
  const [showImageModal, setShowImageModal] = useState(false);
  const [imageBlob, setImageBlob] = useState<string | null>(null);
  const [imageDetections, setImageDetections] = useState<any[]>([]);

  useEffect(() => {
    if (datasetId) {
      loadDataset();
    }
  }, [datasetId]);

  async function loadDataset() {
    try {
      const token = localStorage.getItem('access_token');

      // 데이터셋 정보 조회
      const datasetResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/datasets-2d/${datasetId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!datasetResponse.ok) {
        throw new Error('Failed to load dataset');
      }

      const datasetData = await datasetResponse.json();
      setDataset(datasetData);

      // 이미지 목록 조회
      const imagesResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/datasets-2d/${datasetId}/images?skip=0&limit=100`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (imagesResponse.ok) {
        const imagesData = await imagesResponse.json();
        setImages(imagesData);
      }

      // 메타데이터 조회 (top-classes)
      const metadataResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/datasets-2d/${datasetId}/top-classes?limit=10`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (metadataResponse.ok) {
        const metadataData = await metadataResponse.json();
        setMetadata(metadataData);
      }

    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  const handleViewImage = async (image: any) => {
    try {
      const token = localStorage.getItem('access_token');
      console.log('Loading image:', image.storage_key);

      // 이미지 로드
      const imageResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/storage/${image.storage_key}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!imageResponse.ok) {
        const errorText = await imageResponse.text();
        console.error('Error response:', errorText);
        alert(`Failed to load image: ${imageResponse.status} - ${errorText}`);
        return;
      }

      const blob = await imageResponse.blob();
      const blobUrl = window.URL.createObjectURL(blob);

      // Detection 정보 로드 (실패해도 이미지는 표시)
      let detections = [];
      try {
        const detectionsResponse = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/images/${image.id}/detections`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (detectionsResponse.ok) {
          detections = await detectionsResponse.json();
          console.log('Loaded detections:', detections.length);
        }
      } catch (err) {
        console.log('No detections available for this image');
      }

      setImageBlob(blobUrl);
      setSelectedImage(image);
      setImageDetections(detections);
      setShowImageModal(true);
    } catch (err) {
      console.error('Error loading image:', err);
      alert(`Error loading image: ${err}`);
    }
  };

  const handleDownloadImage = async (image: any) => {
    try {
      const token = localStorage.getItem('access_token');
      console.log('Downloading image:', image.storage_key);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/storage/${image.storage_key}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      console.log('Download response status:', response.status);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = image.file_name;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const errorText = await response.text();
        console.error('Download error:', errorText);
        alert(`Failed to download image: ${response.status} - ${errorText}`);
      }
    } catch (err) {
      console.error('Error downloading image:', err);
      alert(`Error downloading image: ${err}`);
    }
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!dataset) {
    return <div>Dataset not found</div>;
  }

  return (
    <div>
      <h2>Dataset: {dataset.name}</h2>

      <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: '#f5f5f5' }}>
        <p><strong>Description:</strong> {dataset.description || 'N/A'}</p>
        <p><strong>Storage Path:</strong> {dataset.storage_path}</p>
        <p><strong>Created:</strong> {new Date(dataset.created_at).toLocaleString()}</p>
        <p><strong>Total Images:</strong> {images.length}</p>
        {metadata && metadata.source === 'metadata' && (
          <p><strong>Metadata Available:</strong> Yes ({metadata.top_classes?.length || 0} classes detected)</p>
        )}
      </div>

      {/* Tabs */}
      <div style={{ marginBottom: '10px', borderBottom: '2px solid #ccc' }}>
        <button
          onClick={() => setActiveTab('images')}
          style={{
            padding: '10px 20px',
            border: 'none',
            backgroundColor: activeTab === 'images' ? '#007bff' : '#f0f0f0',
            color: activeTab === 'images' ? 'white' : 'black',
            cursor: 'pointer',
          }}
        >
          Images ({images.length})
        </button>
        <button
          onClick={() => setActiveTab('metadata')}
          style={{
            padding: '10px 20px',
            border: 'none',
            backgroundColor: activeTab === 'metadata' ? '#007bff' : '#f0f0f0',
            color: activeTab === 'metadata' ? 'white' : 'black',
            cursor: 'pointer',
            marginLeft: '5px',
          }}
        >
          Metadata
        </button>
      </div>

      {/* Images Tab */}
      {activeTab === 'images' && (
        <div>
          <h3>Images</h3>
          {images.length === 0 ? (
            <p>No images in this dataset</p>
          ) : (
            <table border={1} cellPadding={5} style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Dimensions</th>
                  <th>Type</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {images.map((image) => (
                  <tr key={image.id}>
                    <td>{image.file_name}</td>
                    <td>
                      {image.width && image.height
                        ? `${image.width} x ${image.height}`
                        : 'N/A'}
                    </td>
                    <td>{image.mime_type || 'N/A'}</td>
                    <td>{new Date(image.created_at).toLocaleString()}</td>
                    <td>
                      <button
                        onClick={() => handleViewImage(image)}
                        style={{ marginRight: '5px' }}
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDownloadImage(image)}
                      >
                        Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Metadata Tab */}
      {activeTab === 'metadata' && (
        <div>
          <h3>Inference Metadata</h3>
          {!metadata || metadata.source === 'none' ? (
            <div style={{ padding: '20px', backgroundColor: '#fff3cd', border: '1px solid #ffc107' }}>
              <p><strong>No metadata available</strong></p>
              <p>Upload this dataset with inference metadata JSON file to see class statistics.</p>
            </div>
          ) : (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <p><strong>Dataset:</strong> {metadata.dataset_name}</p>
                <p><strong>Total Images:</strong> {metadata.total_images}</p>
                <p><strong>Source:</strong> Pre-computed metadata (fast query)</p>
              </div>

              <h4>Top Classes Detected</h4>
              <table border={1} cellPadding={5} style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Class Name</th>
                    <th>Detection Count</th>
                    <th>Percentage</th>
                    <th>Avg Confidence</th>
                    <th>Images</th>
                  </tr>
                </thead>
                <tbody>
                  {metadata.top_classes?.map((cls: any, index: number) => (
                    <tr key={index}>
                      <td><strong>{cls.class_name}</strong></td>
                      <td>{cls.count}</td>
                      <td>{cls.percentage}%</td>
                      <td>{cls.avg_confidence}</td>
                      <td>{cls.image_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {metadata.top_classes?.length === 0 && (
                <p style={{ marginTop: '10px', color: '#888' }}>No classes detected in metadata</p>
              )}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: '20px' }}>
        <button onClick={() => window.history.back()}>
          ← Back to Datasets
        </button>
      </div>

      {/* Image Modal */}
      {showImageModal && selectedImage && imageBlob && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => {
            setShowImageModal(false);
            if (imageBlob) {
              window.URL.revokeObjectURL(imageBlob);
              setImageBlob(null);
            }
            setImageDetections([]);
          }}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '20px',
              maxWidth: '90%',
              maxHeight: '90%',
              overflow: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ marginBottom: '10px' }}>
              <h3>{selectedImage.file_name}</h3>
              <p>
                {selectedImage.width} x {selectedImage.height} | {selectedImage.mime_type}
              </p>
            </div>

            <div style={{ position: 'relative' }}>
              <img
                src={imageBlob}
                alt={selectedImage.file_name}
                style={{ maxWidth: '100%', maxHeight: '60vh', display: 'block' }}
              />
            </div>

            {/* Detection Metadata */}
            {imageDetections && imageDetections.length > 0 && (
              <div style={{ marginTop: '20px', borderTop: '2px solid #ccc', paddingTop: '10px' }}>
                <h4>Inference Metadata ({imageDetections.length} detections)</h4>
                <table border={1} cellPadding={5} style={{ width: '100%', fontSize: '12px' }}>
                  <thead>
                    <tr>
                      <th>Class</th>
                      <th>Confidence</th>
                      <th>BBox</th>
                    </tr>
                  </thead>
                  <tbody>
                    {imageDetections.slice(0, 10).map((det, idx) => (
                      <tr key={idx}>
                        <td><strong>{det.class_name}</strong></td>
                        <td>{(det.confidence * 100).toFixed(1)}%</td>
                        <td style={{ fontSize: '10px' }}>
                          ({det.bbox.x1.toFixed(0)}, {det.bbox.y1.toFixed(0)}) -
                          ({det.bbox.x2.toFixed(0)}, {det.bbox.y2.toFixed(0)})
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {imageDetections.length > 10 && (
                  <p style={{ marginTop: '5px', color: '#666', fontSize: '12px' }}>
                    ... and {imageDetections.length - 10} more detections
                  </p>
                )}
              </div>
            )}

            {imageDetections && imageDetections.length === 0 && (
              <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#f0f0f0' }}>
                <p style={{ margin: 0, fontSize: '12px', color: '#666' }}>
                  No inference metadata available for this image
                </p>
              </div>
            )}

            <div style={{ marginTop: '10px' }}>
              <button onClick={() => {
                setShowImageModal(false);
                if (imageBlob) {
                  window.URL.revokeObjectURL(imageBlob);
                  setImageBlob(null);
                }
                setImageDetections([]);
              }}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
