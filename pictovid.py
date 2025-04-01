import cv2
import os

def create_video_from_images(image_folder, output_video, frame_rate):

    images = [img for img in os.listdir(image_folder) if img.startswith("frame2_") and img.endswith(".jpg")]
    images.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))

    first_image_path = os.path.join(image_folder, images[0])
    first_image = cv2.imread(first_image_path)
    height,width,layers = first_image.shape

    video_writer = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), frame_rate, (width, height))

    for image_name in images:
        image_path = os.path.join(image_folder, image_name)
        frame = cv2.imread(image_path)
        video_writer.write(frame)

    video_writer.release()

    print("videosaved as {output_video}")

if __name__ == "__main__":

    image_folder = "captures"
    output_video = "output.mp4"
    frame_rate = 30

    create_video_from_images(image_folder, output_video, frame_rate)
