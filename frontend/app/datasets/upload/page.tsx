'use client';

import { useState } from 'react';

export default function UploadDatasetPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasetName, setDatasetName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [imageCount, setImageCount] = useState(0);
  const [metadataCount, setMetadataCount] = useState(0);

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFiles(e.target.files);

      // 이미지와 JSON 파일 개수 세기
      let images = 0;
      let metadata = 0;
      for (let i = 0; i < e.target.files.length; i++) {
        const file = e.target.files[i];
        if (file.type.startsWith('image/')) {
          images++;
        } else if (file.name.endsWith('.json')) {
          metadata++;
        }
      }
      setImageCount(images);
      setMetadataCount(metadata);
    }
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedFiles || selectedFiles.length === 0) {
      setError('이미지 파일 또는 폴더를 선택해주세요.');
      return;
    }

    if (!datasetName.trim()) {
      setError('데이터셋 이름을 입력해주세요.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('dataset_name', datasetName);
      if (description) {
        formData.append('description', description);
      }

      // 이미지 파일과 JSON 메타데이터 파일 분리
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        if (file.type.startsWith('image/')) {
          formData.append('images', file);
        } else if (file.name.endsWith('.json')) {
          formData.append('metadata', file);
        }
      }

      const token = localStorage.getItem('access_token');
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/dataset-service/upload-multipart`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();

      if (result.metadata_processed) {
        alert(
          `Dataset uploaded successfully!\n` +
          `${result.image_count} images\n` +
          `Metadata analyzed (${result.metadata_stats.total_detections} detections)`
        );
      } else {
        alert(`Dataset uploaded successfully! ${result.image_count} images`);
      }

      window.location.href = '/datasets';
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h2>Upload Dataset</h2>

      {error && (
        <div style={{ border: '1px solid red', padding: '10px', marginBottom: '20px' }}>
          Error: {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label>
            Dataset Name *
            <br />
            <input
              type="text"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              required
              style={{ width: '100%', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Description
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              style={{ width: '100%', padding: '5px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label>
            Select Image Folder *
            <br />
            <input
              type="file"
              onChange={handleFolderSelect}
              // @ts-ignore - webkitdirectory is non-standard but supported
              webkitdirectory="true"
              directory="true"
              multiple
              style={{ width: '100%', padding: '5px' }}
            />
            {selectedFiles && (
              <div>
                <small>
                  {imageCount} image(s) selected
                  {metadataCount > 0 && `, ${metadataCount} metadata file(s) found`}
                </small>
              </div>
            )}
            <small>폴더 내 JSON 파일은 자동으로 메타데이터로 인식됩니다.</small>
          </label>
        </div>

        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f0f0f0' }}>
          <h4>Metadata Benefits</h4>
          <p>
            If you provide inference metadata:
          </p>
          <ul>
            <li>750x faster class statistics (10ms vs 7.5s)</li>
            <li>Pre-calculated top classes for attack targeting</li>
            <li>Detection counts and confidence scores</li>
          </ul>
        </div>

        <div>
          <button type="button" onClick={() => window.history.back()}>
            Cancel
          </button>
          {' '}
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Uploading...' : 'Upload Dataset'}
          </button>
        </div>
      </form>
    </div>
  );
}
