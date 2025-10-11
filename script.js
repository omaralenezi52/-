// بيانات الأغاني (المسارات التي يجب أن تضعها في مجلد 'tracks')
const trackList = [
    { 
        name: "عبدالله السالم - جلسة مع الفنان فهد عبدالمحسن (الوجه الأول)", 
        artist: "عبدالله السالم", 
        path: "tracks/song1_wajh_awal.mp3",
        cover: "images/cover1.jpg" // يمكنك إضافة مسارات صور الغلاف هنا
    },
    { 
        name: "عبدالله السالم - جلسة مع الفنان فهد عبدالمحسن (الوجه الثاني)", 
        artist: "عبدالله السالم", 
        path: "tracks/song2_wajh_thani.mp3",
        cover: "images/cover2.jpg"
    },
    { 
        name: "اضحك واخفي حزن الايام عندي صافية", 
        artist: "عبدالله السالم", 
        path: "tracks/song3_id7ak.mp3",
        cover: "images/cover3.jpg"
    }
    // أضف المزيد من الأغاني هنا بنفس التنسيق
];

// تحديد عناصر المشغل من الـ HTML
const audioPlayer = document.getElementById('audio-player');
const playPauseBtn = document.getElementById('play-pause-btn');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const seekSlider = document.getElementById('seek-slider');
const volumeSlider = document.getElementById('volume-slider');
const currentTimeDisplay = document.querySelector('.current-time');
const totalDurationDisplay = document.querySelector('.total-duration');
const trackNameDisplay = document.querySelector('.track-name');
const artistNameDisplay = document.querySelector('.artist-name');
const trackArt = document.querySelector('.track-art');
const playerContainer = document.querySelector('.player-container');
const playlist = document.getElementById('playlist');

let trackIndex = 0;
let isPlaying = false;

// 1. دالة تهيئة قائمة الأغاني (Playlist)
function renderPlaylist() {
    playlist.innerHTML = ''; // تفريغ القائمة أولاً
    trackList.forEach((track, index) => {
        const li = document.createElement('li');
        li.textContent = `${track.name}`;
        li.dataset.index = index;
        if (index === trackIndex) {
            li.classList.add('active');
        }
        li.addEventListener('click', () => {
            loadTrack(index);
            playPauseTrack(true);
        });
        playlist.appendChild(li);
    });
}

// 2. دالة تحميل الأغنية
function loadTrack(index) {
    trackIndex = index;
    const track = trackList[trackIndex];
    audioPlayer.src = track.path;
    trackNameDisplay.textContent = track.name;
    artistNameDisplay.textContent = track.artist;
    // تحديث غلاف الأغنية
    trackArt.style.backgroundImage = `url('${track.cover}')`;
    
    // تحديث حالة الأغنية في القائمة
    document.querySelectorAll('#playlist li').forEach((item, i) => {
        item.classList.toggle('active', i === trackIndex);
    });
    
    audioPlayer.load(); // تحميل بيانات الأغنية الجديدة
}

// 3. دالة تشغيل/إيقاف مؤقت
function playPauseTrack(forcePlay = false) {
    if (!isPlaying || forcePlay) {
        audioPlayer.play();
        isPlaying = true;
        playPauseBtn.innerHTML = '<i class="fa fa-pause"></i>';
        playerContainer.classList.add('playing');
    } else {
        audioPlayer.pause();
        isPlaying = false;
        playPauseBtn.innerHTML = '<i class="fa fa-play"></i>';
        playerContainer.classList.remove('playing');
    }
}

// 4. دالة الأغنية التالية
function nextTrack() {
    trackIndex = (trackIndex + 1) % trackList.length;
    loadTrack(trackIndex);
    playPauseTrack(true);
}

// 5. دالة الأغنية السابقة
function prevTrack() {
    trackIndex = (trackIndex - 1 + trackList.length) % trackList.length;
    loadTrack(trackIndex);
    playPauseTrack(true);
}

// 6. تنسيق الوقت (من الثواني إلى الدقائق:الثواني)
function formatTime(seconds) {
    if (isNaN(seconds)) return "0:00";
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs < 10 ? '0' : ''}${secs}`;
}

// =============== معالجات الأحداث (Event Listeners) ===============

// أزرار التحكم
playPauseBtn.addEventListener('click', () => playPauseTrack());
nextBtn.addEventListener('click', nextTrack);
prevBtn.addEventListener('click', prevTrack);

// تحديث شريط التقدم والوقت
audioPlayer.addEventListener('timeupdate', () => {
    const currentTime = audioPlayer.currentTime;
    const duration = audioPlayer.duration;
    
    if (isFinite(duration)) {
        seekSlider.value = (currentTime / duration) * 100;
        currentTimeDisplay.textContent = formatTime(currentTime);
    }
});

// عند تحميل بيانات الأغنية (للحصول على المدة الكلية)
audioPlayer.addEventListener('loadedmetadata', () => {
    const duration = audioPlayer.duration;
    if (isFinite(duration)) {
        totalDurationDisplay.textContent = formatTime(duration);
    } else {
         totalDurationDisplay.textContent = "0:00";
    }
});

// البحث في الأغنية عبر شريط التقدم
seekSlider.addEventListener('input', () => {
    const duration = audioPlayer.duration;
    if (isFinite(duration)) {
        const seekTo = (seekSlider.value / 100) * duration;
        audioPlayer.currentTime = seekTo;
    }
});

// التحكم في مستوى الصوت
volumeSlider.addEventListener('input', () => {
    audioPlayer.volume = volumeSlider.value;
});

// عند انتهاء الأغنية، الانتقال إلى الأغنية التالية
audioPlayer.addEventListener('ended', nextTrack);

// تهيئة المشغل عند التحميل
document.addEventListener('DOMContentLoaded', () => {
    renderPlaylist(); // عرض قائمة الأغاني أولاً
    loadTrack(trackIndex); // تحميل الأغنية الأولى
});