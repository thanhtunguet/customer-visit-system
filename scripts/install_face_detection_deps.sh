#!/bin/bash

# Enhanced Face Detection Dependencies Installation Script
# Run this script to install additional face detection libraries

set -e  # Exit on error

echo "🚀 Installing enhanced face detection dependencies..."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected."
    echo "   It's recommended to run this in a virtual environment."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please activate a virtual environment first."
        exit 1
    fi
fi

echo "📦 Installing core computer vision libraries..."
pip install --upgrade opencv-python-headless
pip install --upgrade pillow
pip install --upgrade numpy

echo "🔍 Installing MTCNN for robust face detection..."
pip install mtcnn tensorflow

echo "🎯 Installing RetinaFace for high-accuracy detection..."
pip install retina-face

echo "🤖 Installing MediaPipe for fast detection..."
pip install mediapipe

echo "🧠 Installing enhanced embedding models..."

# Try to install InsightFace (may require additional system dependencies)
echo "🔬 Installing InsightFace..."
pip install insightface || {
    echo "⚠️  InsightFace installation failed. This may require additional system dependencies."
    echo "   On macOS: brew install cmake"
    echo "   On Ubuntu: apt-get install cmake libopenblas-dev"
    echo "   The system will work without InsightFace using fallback methods."
}

# Try to install DeepFace
echo "🎭 Installing DeepFace..."
pip install deepface || {
    echo "⚠️  DeepFace installation failed. The system will work without it."
}

# Try to install FaceNet PyTorch
echo "🔥 Installing FaceNet PyTorch..."
pip install facenet-pytorch || {
    echo "⚠️  FaceNet PyTorch installation failed. The system will work without it."
}

echo "📊 Installing additional image processing libraries..."
pip install scikit-image
pip install albumentations || echo "⚠️  Albumentations installation failed (optional)"

echo "🧪 Installing optional performance improvements..."
pip install numba || echo "⚠️  Numba installation failed (optional)"

# Download required models
echo "📥 Downloading required models..."

# Create models directory
mkdir -p apps/worker/app/models

# Download OpenCV DNN models
echo "Downloading OpenCV DNN face detection models..."
cd apps/worker/app/models

# Face detection prototxt
if [ ! -f "deploy.prototxt" ]; then
    curl -L -o deploy.prototxt "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
    echo "✅ Downloaded deploy.prototxt"
fi

# Face detection model
if [ ! -f "res10_300x300_ssd_iter_140000.caffemodel" ]; then
    curl -L -o res10_300x300_ssd_iter_140000.caffemodel "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
    echo "✅ Downloaded OpenCV face detection model"
fi

# Try to download YuNet model (optional)
if [ ! -f "yunet.onnx" ]; then
    echo "Trying to download YuNet model..."
    curl -L -o yunet.onnx "https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" || {
        echo "⚠️  YuNet model download failed. Using fallback detectors."
    }
fi

cd - > /dev/null

echo "✨ Installation complete!"
echo ""
echo "🔍 Installed face detection methods:"
echo "  ✅ OpenCV DNN (reliable baseline)"
echo "  ✅ Haar Cascades (fallback)"

# Check which optional libraries were installed
python3 -c "
import sys
optional_libs = [
    ('mtcnn', 'MTCNN'),
    ('retinaface', 'RetinaFace'), 
    ('mediapipe', 'MediaPipe'),
    ('insightface', 'InsightFace'),
    ('deepface', 'DeepFace'),
    ('facenet_pytorch', 'FaceNet PyTorch')
]

print('📊 Optional libraries status:')
for lib, name in optional_libs:
    try:
        __import__(lib)
        print(f'  ✅ {name}')
    except ImportError:
        print(f'  ❌ {name} (fallback methods available)')
"

echo ""
echo "🎯 Next steps:"
echo "1. Test the enhanced face detection with your staff images"
echo "2. The system will automatically select the best available detector"
echo "3. Check logs to see which detectors are being used"
echo ""
echo "💡 For production deployment, consider:"
echo "   - Installing on a GPU-enabled machine for better performance"
echo "   - Using Docker with pre-built images containing all dependencies"
echo "   - Monitoring which detectors work best for your image types"