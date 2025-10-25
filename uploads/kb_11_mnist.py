import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

def create_and_train_model():
    """
    创建并训练手写数字识别模型
    """
    # 加载MNIST数据集
    (x_train, y_train), (x_test, y_test) = keras.datasets.mnist.load_data()
    
    # 数据预处理
    # 归一化像素值到0-1范围
    x_train = x_train.astype("float32") / 255.0
    x_test = x_test.astype("float32") / 255.0
    
    # 调整数据形状，添加通道维度 (28, 28, 1)
    x_train = np.expand_dims(x_train, -1)
    x_test = np.expand_dims(x_test, -1)
    
    # 将标签转换为分类格式
    y_train = keras.utils.to_categorical(y_train, 10)
    y_test = keras.utils.to_categorical(y_test, 10)
    
    # 创建模型
    model = keras.Sequential([
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(28, 28, 1)),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Flatten(),
        layers.Dropout(0.5),
        layers.Dense(128, activation='relu'),
        layers.Dense(10, activation='softmax')
    ])
    
    # 编译模型
    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # 训练模型
    history = model.fit(
        x_train, y_train,
        batch_size=128,
        epochs=10,
        validation_data=(x_test, y_test)
    )
    
    # 保存模型
    model.save('handwriting_model.h5')
    print("模型已保存为 'handwriting_model.h5'")
    
    return model, history

def preprocess_image(image_path):
    """
    预处理图片，使其适合模型输入
    """
    # 打开图片并转换为灰度
    img = Image.open(image_path).convert('L')
    
    # 调整大小为28x28像素
    img = img.resize((28, 28))
    
    # 转换为numpy数组
    img_array = np.array(img)
    
    # 反转颜色（如果背景是白色，数字是黑色）
    # MNIST数据是白底黑字，如果输入是黑底白字需要反转
    if np.mean(img_array) > 127:  # 如果平均像素值较高，说明背景较亮
        img_array = 255 - img_array
    
    # 归一化
    img_array = img_array.astype("float32") / 255.0
    
    # 添加批次和通道维度
    img_array = np.expand_dims(img_array, axis=0)  # 添加批次维度
    img_array = np.expand_dims(img_array, axis=-1)  # 添加通道维度
    
    return img_array

def predict_digit(model, image_path):
    """
    使用训练好的模型预测图片中的数字
    """
    # 预处理图片
    processed_img = preprocess_image(image_path)
    
    # 进行预测
    predictions = model.predict(processed_img)
    
    # 获取预测结果
    predicted_digit = np.argmax(predictions[0])
    confidence = np.max(predictions[0])
    
    return predicted_digit, confidence, predictions[0]

def main():
    """
    主函数
    """
    # 检查模型是否存在，如果不存在则训练
    if os.path.exists('handwriting_model.h5'):
        print("加载已训练的模型...")
        model = keras.models.load_model('handwriting_model.h5')
    else:
        print("训练新模型...")
        model, history = create_and_train_model()
    
    # 查找同目录下的图片文件
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
    image_files = []
    
    for file in os.listdir('.'):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            image_files.append(file)
    
    if not image_files:
        print("在同目录下未找到图片文件！")
        print("支持的格式：", image_extensions)
        return
    
    print("\n找到以下图片文件：")
    for i, file in enumerate(image_files):
        print(f"{i+1}. {file}")
    
    # 让用户选择图片
    try:
        choice = int(input("\n请选择要识别的图片编号：")) - 1
        if choice < 0 or choice >= len(image_files):
            print("无效的选择！")
            return
        
        selected_image = image_files[choice]
        print(f"\n正在识别图片: {selected_image}")
        
        # 进行预测
        digit, confidence, all_probs = predict_digit(model, selected_image)
        
        # 显示结果
        print(f"\n识别结果: 数字 {digit}")
        print(f"置信度: {confidence:.2%}")
        
        print("\n所有数字的概率分布:")
        for i, prob in enumerate(all_probs):
            print(f"数字 {i}: {prob:.2%}")
            
        # 显示图片（可选）
        try:
            img = Image.open(selected_image)
            plt.figure(figsize=(6, 6))
            plt.imshow(img.convert('L'), cmap='gray')
            plt.title(f'预测结果: {digit} (置信度: {confidence:.2%})')
            plt.axis('off')
            plt.show()
        except:
            print("无法显示图片，但预测已完成。")
            
    except ValueError:
        print("请输入有效的数字！")
    except Exception as e:
        print(f"处理图片时出错: {e}")

if __name__ == "__main__":
    # 检查必要的库是否已安装
    try:
        main()
    except ImportError as e:
        print(f"缺少必要的库: {e}")
        print("请安装所需的库: pip install tensorflow pillow matplotlib numpy")