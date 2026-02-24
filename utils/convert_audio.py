import os
import tempfile
import subprocess
from django.core.files import File
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger("project")


def convert_audio_to_mp3(audio_file):
    """
    Convert an uploaded audio file to MP3 format using FFmpeg directly

    Args:
        audio_file: The uploaded file from request.FILES

    Returns:
        A Django File object representing the converted MP3 file
    """
    tmp_orig_path = None
    mp3_temp_path = None

    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(audio_file.name)[1], delete=False
        ) as tmp_orig:
            # Write the uploaded file content to the temp file
            for chunk in audio_file.chunks():
                tmp_orig.write(chunk)
            tmp_orig_path = tmp_orig.name

        # Create another temporary file for the converted MP3
        mp3_temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        mp3_temp_path = mp3_temp.name
        mp3_temp.close()

        # Use FFmpeg directly to convert the file
        try:
            # Run FFmpeg command to convert to MP3
            command = [
                "ffmpeg",
                "-i",
                tmp_orig_path,  # Input file
                "-acodec",
                "libmp3lame",  # MP3 codec
                "-q:a",
                "2",  # Audio quality (2 is good quality, lower is better)
                "-y",  # Overwrite output file if it exists
                mp3_temp_path,  # Output file
            ]

            # Execute the command
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )

            # Check if conversion was successful
            if not os.path.exists(mp3_temp_path) or os.path.getsize(mp3_temp_path) == 0:
                logger.error("FFmpeg conversion failed to produce output file")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion error: {e.stderr.decode()}")
            return None
        finally:
            # Clean up the original temp file
            if os.path.exists(tmp_orig_path):
                os.unlink(tmp_orig_path)
                tmp_orig_path = None

        # Create a ContentFile from the MP3 file - this loads the file into memory
        # but ensures we don't have issues with closed file handles
        filename = os.path.splitext(os.path.basename(audio_file.name))[0] + ".mp3"
        with open(mp3_temp_path, "rb") as f:
            content = f.read()

        # Create a ContentFile which keeps the data in memory
        mp3_file = ContentFile(content, name=filename)

        # Clean up the MP3 temp file since we've read it into memory
        if os.path.exists(mp3_temp_path):
            os.unlink(mp3_temp_path)
            mp3_temp_path = None

        return mp3_file

    except Exception as e:
        logger.error(f"Error converting audio to MP3: {str(e)}", exc_info=True)
        # Clean up temp files in case of error
        if mp3_temp_path and os.path.exists(mp3_temp_path):
            os.unlink(mp3_temp_path)
        if tmp_orig_path and os.path.exists(tmp_orig_path):
            os.unlink(tmp_orig_path)
        return None
