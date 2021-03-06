# findsilence - Split long WAV files into tracks
# Copyright (C) 2008 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" This module provides functionality to split files by silence detection.

The Audio class implements the silence detection while its child classes, like
Wave, MP3 or Ogg, have to implement the file types.

They need to implment these methods: rms, tell, setpos, rewind, readframes, 
write_frames, and the attributes frames and framerate. """

import audioop
import wave
import sys
import os

from findsilence import defaults

__version__ = "0.1rc1"
__author__ = "Florian Mayer <flormayer@aim.com>"
__url__ = ""
__copyright__ = "(c) 2008 Florian Mayer"
__license__ = "GNU General Public License version 3"
__bugs__ = ""



class DummyNotifier(object):
    def current_frame(self, frame):
        pass
    
    def total_frames(self, frames):
        pass
    
    def done(self):
        pass


class DummyThread:
    """ Dummy Thread that is used when the functions are used without
    a parent_thread argument """
    def __init__(self):
        self.notifier = DummyNotifier()
    
    def is_stopped(self):
        return False

        
class Cancelled(Exception):
    """ Raised when silence detection was cancelled by parent thread """
    pass

        
class FileExists(Exception):
    """ This is raised when the directory passed to split_phono is a file """
    pass


class NoSilence(Exception):
    """ Raised when no silence is found in a file """
    pass


class Audio:
    """ This class implements the silence finding. File-type specific mechanics
    have to be overridden by child classes representing the file-types."""
    def __init__(self):
        pass
    
    # These methods and attributes must be overridden by child classes. 
    def rms(self, frames):
        """ Override this to return the root-mean-square of the frames. """
        raise NotImplementedError
    
    def tell(self):
        """ Override this to return current position. """
        raise NotImplementedError
    
    def setpos(self, pos):
        """ Override this to set the current position. """
        raise NotImplementedError
    
    def rewind(self):
        """ Rewind file to beginning. Should be equivalent to setpos(0) """
        raise NotImplementedError
    
    def readframes(self, x):
        """ Override to return x frames from current position. These frames 
        are passed to rms directly. """
        raise NotImplementedError
    
    def write_frames(self, file_name, frames):
        """ Override this to write frames to file_name in the specified 
        file format """
        raise NotImplementedError
    
    @property
    def frames(self):
        """ Total amount of frames """
        raise NotImplementedError
    
    @property
    def framerate(self):
        """ Frames per second """
        raise NotImplementedError
    
    @property
    def max_amplitude(self):
        """ Maximal amplitude in file """
        raise NotImplementedError
    
    @property
    def min_amplitude(self):
        """ Minimum amplitude in file """
        raise NotImplementedError
    
    def median_volume(self):
        """ Median volume for the whole file. 
        
        It returns to the position where
        the file was before after telling the median volume."""
        pos = self.tell()
        self.rewind()
        median_volume = self.rms(self.readframes(self.frames))
        self.setpos(pos)
        return median_volume
    
    def get_silence(self, pause_seconds=2, silence_cap=500, parent_thread=None):
        """ 
        pause_seconds is either an int or a float containing the minimum length 
        of a pause. Silence cap defines what volume level is considered silence.
        """
        last_emitted = None
        # Enable function to run without a parent Thread.
        if parent_thread is None:
            parent_thread = DummyThread()
        # Find out how many frames the passed second value is
        read_frames = int(pause_seconds * self.framerate)
        # Once silence has been found, continue searching in this interval
        afterloop_frames = 20
        frames = self.frames
        initpos = i = self.tell()
        silence = []
        # This scans the file in steps of read_frames whether a section's volume
        # is lower than silence_cap, if it is it is written to silence.
        while i < frames:
            if parent_thread.is_stopped():
                raise Cancelled
            frame = self.readframes(read_frames)
            volume = self.rms(frame)
            if volume < silence_cap:
                # Segment is silence!
                # Continue searching in smaller steps whether the silence is 
                # longer than read_frames but smaller than read_frames*2.
                while volume < silence_cap and self.tell() < self.frames:
                    frame = self.readframes(afterloop_frames)
                    volume = self.rms(frame)
                # If the last sequent of silence ends where the new one starts
                # it's a continous range.
                if silence and silence[-1][1] == i:
                    silence[-1][1] = self.tell()
                else:
                    silence.append([i, self.tell()])
            i = self.tell()
            
            # Prevent callback to happen too often, thus draining performance.
            if last_emitted is None or last_emitted + self.frames / 100 < i:
                last_emitted = i
                # Callback used to update progessbar
                parent_thread.notifier.current_frame(i)
        
        # Return the file to where it was when we got it.
        self.setpos(initpos)
        return silence
    
    def tracks(self, silence, min_length):
        from_pos = 0
        for to_pos, next_from in silence:
            if (to_pos - from_pos) >= min_length * self.framerate:
                # Track is long enough to be considered a track.
                yield from_pos, to_pos
            from_pos = next_from
    
    def track_data(self, tracks):
        for from_pos, to_pos in tracks:
            self.setpos(from_pos)
            yield self.readframes(to_pos - from_pos)

    def split_into(self, tracks, min_length, pause_seconds, parent_thread):
        min_ = self.min_amplitude
        max_ = self.max_amplitude
        while True:
            mid = min_ + (max_ - min_) / 2.0
            
            silence = self.get_silence(
                pause_seconds, mid, parent_thread
            )
            n = len(list(self.tracks(silence, min_length)))
            
            if n == tracks or min_ == max_:
                # Either we're done or we would never be done anyway.
                break
            elif n > tracks:
                # We split too often. Need to consider less as silence.
                max_ = mid
            else:
                # We split too seldom. Need to consider more as silence.
                min_ = mid
    
        return silence

    @classmethod
    def from_file(cls, filename):
        if filename.lower().endswith('.wav'):
            return Wave(filename)
        else:
            raise ValueError


class Wave(wave.Wave_read, Audio):
    """ This class implements the Wave file-type so it is suiteable for use 
    with Audio. It takes most of its methods from wave.Wave_read. """
    def __init__(self, file_name):
        wave.Wave_read.__init__(self, file_name)
        self.width = self.getsampwidth()
        self.frames = self.getnframes()
        self.channels = self.getnchannels()
        self.framerate = self.getframerate()
        
        self._max_amplitude = None
        self._min_amplitude = None
    
    def write_frames(self, file_name, frames):
        """ Write the frames into file_name with the same header as the 
        original file had """
        f = wave.open(file_name, 'wb')
        f.setnchannels(self.channels)
        f.setsampwidth(self.width)
        f.setframerate(self.framerate)
        try:
            f.writeframes(frames)
        finally:
            f.close()
    
    def rms(self, frames):
        """ Get root-mean-square of frames in the wave file """
        return audioop.rms(frames, self.width)
    
    @property
    def max_amplitude(self):
        # This is only an approximation.
        if self._max_amplitude is not None:
            return self._max_amplitude
        
        pos = self.tell()
        self.rewind()
        
        max_ = 0
        read_frames = int(0.5 * self.framerate)
        frame = 0
        while self.tell() < self.frames:
            frames = self.readframes(read_frames)
            rms = self.rms(frames)
            if rms > max_:
                max_ = rms
        self.setpos(pos)
        self._max_amplitude = max_
        return max_
    
    @property
    def min_amplitude(self):
        # This is only an approximation.
        if self._min_amplitude is not None:
            return self._min_amplitude
        
        pos = self.tell()
        self.rewind()
        
        min_ = None
        read_frames = int(0.5 * self.framerate)
        frame = 0
        while self.tell() < self.frames:
            frames = self.readframes(read_frames)
            rms = self.rms(frames)
            if min_ is None or rms < min_:
                min_ = rms
        self.setpos(pos)
        self._min_amplitude = min_
        return min_


class MP3(Audio):
    """ Implement Audio API for MP3 files. This includes the following methods 
    and attributes: rms, tell, setpos, rewind, readframes, write_frames, 
    frames and framerate """
    pass


class Ogg(Audio):
    """ Implement Audio API for ogg files. This includes the following methods 
    and attributes: rms, tell, setpos, rewind, readframes, write_frames, 
    frames and framerate """
    pass


def split_phono(file_name, directory, pause_seconds=2, volume_cap=300, 
                min_length=10, parent_thread=None, tracks=None):
    """ Only change pause_seconds or volume_cap if you are sure what you are 
    doing! They seem to be working pretty good for old records. """
    if parent_thread is None:
        parent_thread = DummyThread()
    if not os.path.exists(directory):
        os.mkdir(directory)
    elif os.path.isfile(directory):
        raise FileExists("The directory you supplied is a file.")
    audio = Audio.from_file(file_name)
    # Callback used to initalize progressbar.
    parent_thread.notifier.total_frames(audio.frames)
    
    if tracks is not None:
        silence = audio.split_into(tracks, min_length, pause_seconds, parent_thread)
    else:
        silence = audio.get_silence(pause_seconds, volume_cap, parent_thread)
    
    if not silence:
        raise NoSilence
    
    split_tracks = audio.track_data(audio.tracks(silence, min_length))
    
    minus = 0
    for i, split_track in enumerate(split_tracks):
        if len(split_track) / (audio.channels * audio.width) \
           < min_length * audio.framerate:
            # Prevent track numbers to be left out because of too short
            # tracks in order to ensure consistency.
            minus += 1
            # Skip tracks shorter than min_length seconds.
            # As on old records that could be the pick-up.
            continue
        f_name = os.path.join(directory, "track_%.2d.wav" % (i - minus))
        audio.write_frames(f_name, split_track)
    # Callback to allow UI to do cleanup actions without needing to worry
    # about the state of the worker Thread.
    parent_thread.notifier.done()
