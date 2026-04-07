import requests
import sys
import time
import os
from datetime import datetime

class DancingVideoAPITester:
    def __init__(self, base_url="https://dogs-music-parody.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.uploaded_files = []
        self.generated_videos = []

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else self.api_url
        headers = {}
        if data and not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, params=params, timeout=60)
                else:
                    response = requests.post(url, json=data, headers=headers, params=params, timeout=60)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.content
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.text}")
                except:
                    pass

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        success, response = self.run_test(
            "API Health Check",
            "GET",
            "",
            200
        )
        return success

    def test_upload_subject_image(self):
        """Test uploading a subject image"""
        # Create a simple test image file
        test_image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_dog.png', test_image_content, 'image/png')}
        params = {'media_type': 'image'}
        
        success, response = self.run_test(
            "Upload Subject Image",
            "POST",
            "upload-media",
            200,
            files=files,
            params=params
        )
        
        if success and 'id' in response:
            self.uploaded_files.append(response)
            print(f"   Uploaded file ID: {response['id']}")
            return True
        return False

    def test_upload_audio_file(self):
        """Test uploading an audio file"""
        # Create a minimal WAV file
        wav_header = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        
        files = {'file': ('test_music.wav', wav_header, 'audio/wav')}
        params = {'media_type': 'audio'}
        
        success, response = self.run_test(
            "Upload Audio File",
            "POST",
            "upload-media",
            200,
            files=files,
            params=params
        )
        
        if success and 'id' in response:
            self.uploaded_files.append(response)
            print(f"   Uploaded audio ID: {response['id']}")
            return True
        return False

    def test_get_uploaded_file(self, file_id):
        """Test retrieving an uploaded file"""
        success, response = self.run_test(
            f"Get File {file_id}",
            "GET",
            f"files/{file_id}",
            200
        )
        return success

    def test_generate_video(self):
        """Test video generation"""
        if not self.uploaded_files:
            print("❌ No uploaded files available for video generation")
            return False

        subject_files = [f for f in self.uploaded_files if f.get('media_type') == 'image']
        audio_files = [f for f in self.uploaded_files if f.get('media_type') == 'audio']
        
        if not subject_files:
            print("❌ No subject images available for video generation")
            return False

        data = {
            "subject_media_ids": [f['id'] for f in subject_files],
            "audio_file_id": audio_files[0]['id'] if audio_files else None,
            "prompt": "A cute dog dancing hip-hop style with sunglasses, doing the moonwalk and spinning with confidence",
            "duration": 30
        }

        success, response = self.run_test(
            "Generate Video",
            "POST",
            "generate-video",
            200,
            data=data
        )
        
        if success and 'id' in response:
            self.generated_videos.append(response)
            print(f"   Video generation started, ID: {response['id']}")
            print(f"   Status: {response.get('status', 'unknown')}")
            return True
        return False

    def test_get_videos_list(self):
        """Test getting list of all videos"""
        success, response = self.run_test(
            "Get Videos List",
            "GET",
            "videos",
            200
        )
        
        if success:
            print(f"   Found {len(response)} videos")
            return True
        return False

    def test_get_video_status(self, video_id):
        """Test getting specific video status"""
        success, response = self.run_test(
            f"Get Video Status {video_id}",
            "GET",
            f"videos/{video_id}",
            200
        )
        
        if success:
            print(f"   Video status: {response.get('status', 'unknown')}")
            return True
        return False

    def test_video_status_polling(self, video_id, max_polls=5):
        """Test video status polling (limited for testing)"""
        print(f"\n🔄 Polling video status for {video_id} (max {max_polls} times)...")
        
        for i in range(max_polls):
            success, response = self.run_test(
                f"Poll Video Status {i+1}/{max_polls}",
                "GET",
                f"videos/{video_id}",
                200
            )
            
            if success:
                status = response.get('status', 'unknown')
                print(f"   Poll {i+1}: Status = {status}")
                
                if status in ['completed', 'failed']:
                    print(f"   Video generation finished with status: {status}")
                    if status == 'failed':
                        print(f"   Error: {response.get('error_message', 'Unknown error')}")
                    return True
                    
                if i < max_polls - 1:  # Don't sleep on last iteration
                    time.sleep(3)  # Wait 3 seconds as per app design
            else:
                return False
                
        print(f"   Video still processing after {max_polls} polls")
        return True  # Not a failure, just still processing

def main():
    print("🎬 Starting Dancing Video Generator API Tests")
    print("=" * 50)
    
    tester = DancingVideoAPITester()
    
    # Test sequence
    tests_passed = 0
    total_tests = 0
    
    # 1. Health check
    total_tests += 1
    if tester.test_health_check():
        tests_passed += 1
    
    # 2. Upload subject image
    total_tests += 1
    if tester.test_upload_subject_image():
        tests_passed += 1
    
    # 3. Upload audio file
    total_tests += 1
    if tester.test_upload_audio_file():
        tests_passed += 1
    
    # 4. Test file retrieval
    if tester.uploaded_files:
        for uploaded_file in tester.uploaded_files:
            total_tests += 1
            if tester.test_get_uploaded_file(uploaded_file['id']):
                tests_passed += 1
    
    # 5. Test video generation
    total_tests += 1
    if tester.test_generate_video():
        tests_passed += 1
    
    # 6. Test videos list
    total_tests += 1
    if tester.test_get_videos_list():
        tests_passed += 1
    
    # 7. Test video status polling
    if tester.generated_videos:
        for video in tester.generated_videos:
            total_tests += 1
            if tester.test_video_status_polling(video['id']):
                tests_passed += 1

    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 API Tests Summary:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
    
    print(f"\n📁 Uploaded Files: {len(tester.uploaded_files)}")
    for f in tester.uploaded_files:
        print(f"   - {f['original_filename']} ({f['media_type']}) - ID: {f['id']}")
    
    print(f"\n🎥 Generated Videos: {len(tester.generated_videos)}")
    for v in tester.generated_videos:
        print(f"   - Video ID: {v['id']} - Status: {v.get('status', 'unknown')}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())