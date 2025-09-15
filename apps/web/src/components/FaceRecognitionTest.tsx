import React, { useState } from 'react';
import {
  Upload,
  Button,
  Card,
  Progress,
  Alert,
  Table,
  Space,
  Typography,
  Tag,
  Image,
  Divider
} from 'antd';
import {
  UploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExperimentOutlined
} from '@ant-design/icons';
import { FaceRecognitionTestResult, FaceRecognitionMatch } from '../types/api';
import { apiClient } from '../services/api';

const { Title, Text } = Typography;

interface FaceRecognitionTestProps {
  staffId: string;
  staffName: string;
}

export const FaceRecognitionTest: React.FC<FaceRecognitionTestProps> = ({
  staffId,
  staffName
}) => {
  const [testImage, setTestImage] = useState<string | null>(null);
  const [testImageUrl, setTestImageUrl] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<FaceRecognitionTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Handle test image upload
  const handleImageUpload = async (file: File) => {
    try {
      // Convert to base64
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      setTestImage(base64);
      setTestImageUrl(URL.createObjectURL(file));
      setTestResult(null);
      setError(null);
    } catch (error) {
      setError('Failed to process image');
    }
  };

  // Run recognition test
  const runTest = async () => {
    if (!testImage) return;

    try {
      setTesting(true);
      setError(null);
      
      const result = await apiClient.testFaceRecognition(staffId, testImage);
      setTestResult(result);
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Recognition test failed');
      setTestResult(null);
    } finally {
      setTesting(false);
    }
  };

  // Clear test
  const clearTest = () => {
    setTestImage(null);
    setTestImageUrl(null);
    setTestResult(null);
    setError(null);
  };

  const getSimilarityColor = (similarity: number) => {
    if (similarity >= 0.9) return 'success';
    if (similarity >= 0.7) return 'warning';
    return 'error';
  };

  const getSimilarityText = (similarity: number) => {
    if (similarity >= 0.9) return 'Excellent Match';
    if (similarity >= 0.7) return 'Good Match';
    if (similarity >= 0.5) return 'Weak Match';
    return 'No Match';
  };

  const columns = [
    {
      title: 'Rank',
      dataIndex: 'rank',
      key: 'rank',
      width: 60,
      render: (_: any, __: any, index: number) => (
        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
          index === 0 ? 'bg-gold text-white' : 
          index === 1 ? 'bg-gray-400 text-white' : 
          index === 2 ? 'bg-orange-400 text-white' : 
          'bg-gray-200 text-gray-600'
        }`}>
          {index + 1}
        </div>
      ),
    },
    {
      title: 'Staff Name',
      dataIndex: 'staff_name',
      key: 'staff_name',
      render: (name: string, record: FaceRecognitionMatch) => (
        <Space>
          <span className="font-medium">{name}</span>
          {record.staff_id === staffId && (
            <Tag color="blue" size="small">Target</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Staff ID',
      dataIndex: 'staff_id',
      key: 'staff_id',
      render: (id: number) => (
        <span className="font-mono text-sm text-gray-600">{id}</span>
      ),
    },
    {
      title: 'Similarity',
      dataIndex: 'similarity',
      key: 'similarity',
      render: (similarity: number) => (
        <Space direction="vertical" size="small" className="w-full">
          <Progress
            percent={similarity * 100}
            size="small"
            status={getSimilarityColor(similarity)}
            showInfo={false}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono">{(similarity * 100).toFixed(1)}%</span>
            <Tag 
              color={getSimilarityColor(similarity)} 
              size="small"
            >
              {getSimilarityText(similarity)}
            </Tag>
          </div>
        </Space>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={4} className="mb-0">
          <ExperimentOutlined className="mr-2" />
          Customer Recognition Test
        </Title>
        {testImage && (
          <Button onClick={clearTest}>
            Clear Test
          </Button>
        )}
      </div>

      <Alert
        message="Test Recognition Accuracy"
        description={`Upload a photo to test how well the system can recognize ${staffName}. The system will compare against all enrolled staff members.`}
        type="info"
        showIcon
      />

      {/* Upload Section */}
      <Card>
        <div className="text-center space-y-2">
          {!testImageUrl ? (
            <Upload.Dragger
              accept="image/*"
              showUploadList={false}
              beforeUpload={(file) => {
                handleImageUpload(file);
                return false;
              }}
              className="rounded-lg p-6"
            >
              <p className="ant-upload-drag-icon">
                <UploadOutlined className="text-4xl text-gray-400" />
              </p>
              <p className="ant-upload-text">
                Click or drag a test image here
              </p>
              <p className="ant-upload-hint">
                Supports JPG, PNG, GIF formats. Best results with clear face photos.
              </p>
            </Upload.Dragger>
          ) : (
            <div className="space-y-4">
              <div className="flex justify-center">
                <Image
                  src={testImageUrl}
                  alt="Test image"
                  style={{ maxWidth: 300, maxHeight: 300 }}
                  className="rounded-lg shadow-md"
                />
              </div>
              
              <Button
                type="primary"
                icon={<ExperimentOutlined />}
                loading={testing}
                onClick={runTest}
                size="large"
              >
                Run Recognition Test
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert
          message="Test Failed"
          description={error}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
        />
      )}

      {/* Results Section */}
      {testResult && (
        <div className="space-y-4">
          <Divider>Recognition Results</Divider>
          
          {/* Processing Info */}
          <Card size="small">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-blue-600">
                  {testResult.processing_info.test_face_detected ? (
                    <CheckCircleOutlined />
                  ) : (
                    <CloseCircleOutlined />
                  )}
                </div>
                <div className="text-sm text-gray-600">Face Detection</div>
                <div className="text-xs text-gray-400">
                  {testResult.processing_info.test_face_detected ? 'Success' : 'Failed'}
                </div>
              </div>
              
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {(testResult.processing_info.test_confidence * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-600">Detection Confidence</div>
                <div className="text-xs text-gray-400">Face quality score</div>
              </div>
              
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {testResult.processing_info.total_staff_compared}
                </div>
                <div className="text-sm text-gray-600">Staff Compared</div>
                <div className="text-xs text-gray-400">Total enrolled faces</div>
              </div>
            </div>
          </Card>

          {/* Best Match */}
          {testResult.best_match && (
            <Card size="small">
              <div className="flex items-center justify-between">
                <div>
                  <Text strong className="text-green-600">Best Match Found</Text>
                  <div className="mt-1">
                    <Space>
                      <span className="font-medium">{testResult.best_match.staff_name}</span>
                      <Tag color="blue">ID: {testResult.best_match.staff_id}</Tag>
                      {testResult.best_match.staff_id === staffId && (
                        <Tag color="success">✓ Correct Match</Tag>
                      )}
                    </Space>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-600">
                    {(testResult.best_match.similarity * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-600">Similarity</div>
                </div>
              </div>
            </Card>
          )}

          {/* All Matches Table */}
          <Card title="All Recognition Results" size="small">
            <Table
              columns={columns}
              dataSource={testResult.matches}
              rowKey={(record) => `${record.staff_id}-${record.image_id || 'primary'}`}
              pagination={false}
              size="small"
            />
          </Card>

          {/* Analysis */}
          {testResult.matches.length > 0 && (
            <Card title="Analysis" size="small">
              <div className="space-y-2 text-sm">
                {testResult.best_match?.staff_id === staffId ? (
                  <div className="flex items-center space-x-2 text-green-600">
                    <CheckCircleOutlined />
                    <span>Recognition successful! The system correctly identified {staffName}.</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 text-red-600">
                    <CloseCircleOutlined />
                    <span>
                      Recognition failed. The system identified a different person or no one above the confidence threshold.
                    </span>
                  </div>
                )}
                
                <div className="text-gray-600">
                  <strong>Recommendations:</strong>
                  {testResult.processing_info.test_confidence < 0.8 && (
                    <span> Try using a clearer image with better lighting and a direct face view.</span>
                  )}
                  {testResult.best_match && testResult.best_match.similarity < 0.7 && (
                    <span> Consider adding more face images to improve recognition accuracy.</span>
                  )}
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
