from flask import Flask, render_template, request, redirect, url_for, send_from_directory,send_file
import os
from werkzeug.utils import secure_filename
from PIL import Image, ImageFilter
from torchvision import transforms
from piq import ssim
from shutil import copy
from flask import request, jsonify
from zipfile import ZipFile
from shutil import move
from io import BytesIO

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
BLURRED_FOLDER = 'mobileblur'  # New folder for blurred images
ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif']

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BLURRED_FOLDER'] = BLURRED_FOLDER  # Added blurred folder path

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_ssim(img_tensor, ref_img):
    return ssim(img_tensor, ref_img).item()

def process_images(source_folder, reference_folder, threshold):
    os.makedirs('good', exist_ok=True)
    os.makedirs('bad', exist_ok=True)

    for (filename, filename2) in zip(os.listdir(source_folder), os.listdir(reference_folder)):
        if (filename.endswith(".JPG") and filename2.endswith(".JPG")) or (filename.endswith(".png") and filename2.endswith(".png")) or (filename.endswith(".jpg") and filename2.endswith(".jpg")) :
            image_path = os.path.join(source_folder, filename)
            img = Image.open(image_path).convert('RGB')
            img_tensor = transforms.ToTensor()(img).unsqueeze(0)

            image_path2 = os.path.join(reference_folder, filename2)
            ref_img = Image.open(image_path2).convert('RGB')
            ref_img_tensor = transforms.ToTensor()(ref_img).unsqueeze(0)

            ssim_score = calculate_ssim(img_tensor, ref_img_tensor)

            print(f"DSSIM score for {filename}: {(1-ssim_score)/2}")

            ssim_score = (1 - ssim_score) / 2
            # print(f"SSIM score for {filename}: {ssim_score}")


            if ssim_score >= threshold:
                destination_path = os.path.join('good', filename)
            else:
                destination_path = os.path.join('bad', filename)

            copy(image_path, destination_path)

def add_blur_to_images(input_folder, output_folder, blur_radius=2):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        try:
            with Image.open(input_path) as img:
                blurred_img = img.filter(ImageFilter.GaussianBlur(blur_radius))
                blurred_img.save(output_path)
        except Exception as e:
            print(f"Error processing {input_path}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_get',methods=['GET'])
def upload_get():
    return render_template('Upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    files = request.files.getlist('file')

    if all(file.filename == '' for file in files):
        return redirect(request.url)

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Call the function to add blur to images after uploading
    add_blur_to_images(UPLOAD_FOLDER, app.config['BLURRED_FOLDER'])

    process_images(UPLOAD_FOLDER,BLURRED_FOLDER, 0.11)

    return redirect(url_for('good_images'))


@app.route('/good')
def good_images():
    image_files = os.listdir('good')
    image_urls = [url_for('uploaded_file', folder='good', filename=image) for image in image_files]
    return render_template('GoodImages.html', image_urls=image_urls)

@app.route('/bad')
def bad_images():
    image_files = os.listdir('bad')
    image_urls = [url_for('uploaded_file', folder='bad', filename=image) for image in image_files]
    return render_template('BadImages.html', image_urls=image_urls)

@app.route('/download')
def download():
    return render_template('Download.html')


@app.route('/uploads/<folder>/<filename>')
def uploaded_file(folder, filename):
    return send_from_directory(folder, filename)

@app.route('/remove_images', methods=['POST'])
def remove_images():
    folder = request.json.get('folder')
    selected_image_urls = request.json.get('selectedImageURLs', [])

    for image_url in selected_image_urls:
        # Build the source and destination file paths
        source_path = os.path.join(folder, os.path.basename(image_url))
        if folder == 'good':
            destination_path = os.path.join('bad', os.path.basename(image_url))
        else:
            destination_path = os.path.join('good', os.path.basename(image_url))

        try:
            # Move the file from the source (good) to the destination (bad) folder
            move(source_path, destination_path)
        except Exception as e:
            print(f"Error moving image {image_url} to bad folder: {e}")

    return jsonify({'message': 'Images moved to bad folder successfully'})


@app.route('/download_images', methods=['GET'])
def download_images():
    good_folder_path = 'good'

    # Create a zip file in memory
    zip_data = BytesIO()
    with ZipFile(zip_data, 'w') as zip_file:
        # Add all files from the good folder to the zip file
        for file_name in os.listdir(good_folder_path):
            file_path = os.path.join(good_folder_path, file_name)
            zip_file.write(file_path, file_name)

    # Rewind the zip file to the beginning
    zip_data.seek(0)

    # Return the zip file as a response
    return send_file(zip_data, mimetype='application/zip', as_attachment=True, download_name='good_images.zip')

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('good', exist_ok=True)
    os.makedirs('bad', exist_ok=True)
    app.run(debug=True)