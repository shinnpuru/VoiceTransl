# Copied from https://github.com/seanghay/uvr-mdx-infer/blob/main/separate.py

import soundfile as sf
import os 
import platform
import librosa
import numpy as np
import onnxruntime as ort
from pathlib import Path
from argparse import ArgumentParser
from tqdm import tqdm


class ConvTDFNet:
    def __init__(self, target_name, L, dim_f, dim_t, n_fft, hop=1024):
        super(ConvTDFNet, self).__init__()
        self.dim_c = 4
        self.dim_f = dim_f
        self.dim_t = 2**dim_t
        self.n_fft = n_fft
        self.hop = hop
        self.n_bins = self.n_fft // 2 + 1
        self.chunk_size = hop * (self.dim_t - 1)
        self.target_name = target_name
        
        out_c = self.dim_c * 4 if target_name == "*" else self.dim_c
        
        self.freq_pad = np.zeros(
            [1, out_c, self.n_bins - self.dim_f, self.dim_t], dtype=np.float32
        )
        self.n = L // 2

    def stft(self, x):
        x = x.reshape([-1, self.chunk_size])
        x = librosa.stft(
            x,
            n_fft=self.n_fft,
            hop_length=self.hop,
            window="hann",
            center=True,
            pad_mode="reflect",
        )
        x = np.stack((x.real, x.imag), axis=1)
        x = x.reshape([-1, 2, 2, self.n_bins, self.dim_t]).reshape(
            [-1, self.dim_c, self.n_bins, self.dim_t]
        )
        return np.ascontiguousarray(x[:, :, : self.dim_f], dtype=np.float32)

    # Inversed Short-time Fourier transform (STFT).
    def istft(self, x, freq_pad=None):
        freq_pad = (
            np.repeat(self.freq_pad, x.shape[0], axis=0)
            if freq_pad is None
            else freq_pad
        )
        x = np.concatenate([x, freq_pad], axis=-2)
        c = 4 * 2 if self.target_name == "*" else 2
        x = x.reshape([-1, c, 2, self.n_bins, self.dim_t])
        x = x[:, :, 0] + 1j * x[:, :, 1]
        x = librosa.istft(
            x,
            n_fft=self.n_fft,
            hop_length=self.hop,
            window="hann",
            center=True,
            length=self.chunk_size,
        )
        return x.reshape([-1, c, self.chunk_size])

class Predictor:
    def __init__(self, args):
        self.args = args
        self.model_ = ConvTDFNet(
            target_name="vocals",
            L=11,
            dim_f=args["dim_f"], 
            dim_t=args["dim_t"], 
            n_fft=args["n_fft"]
        )
        
        self.model = ort.InferenceSession(
            args["model_path"],
            providers=self._get_providers(),
        )

    def _get_providers(self):
        system = platform.system()
        if system == "Windows":
            return ["DmlExecutionProvider"]
        if system == "Darwin":
            return ["CoreMLExecutionProvider"]
        return ["CPUExecutionProvider"]

    def demix(self, mix):
        samples = mix.shape[-1]
        margin = self.args["margin"]
        chunk_size = self.args["chunks"] * 44100
        
        assert not margin == 0, "margin cannot be zero!"
        
        if margin > chunk_size:
            margin = chunk_size

        segmented_mix = {}

        if self.args["chunks"] == 0 or samples < chunk_size:
            chunk_size = samples

        counter = -1
        for skip in range(0, samples, chunk_size):
            counter += 1
            s_margin = 0 if counter == 0 else margin
            end = min(skip + chunk_size + margin, samples)
            start = skip - s_margin
            segmented_mix[skip] = mix[:, start:end].copy()
            if end == samples:
                break

        sources = self.demix_base(segmented_mix, margin_size=margin)
        return sources

    def demix_base(self, mixes, margin_size):
        chunked_sources = []
        progress_bar = tqdm(total=len(mixes))
        progress_bar.set_description("Processing")
        
        for mix in mixes:
            cmix = mixes[mix]
            sources = []
            n_sample = cmix.shape[1]
            model = self.model_
            trim = model.n_fft // 2
            gen_size = model.chunk_size - 2 * trim
            pad = gen_size - n_sample % gen_size
            mix_p = np.concatenate(
                (np.zeros((2, trim)), cmix, np.zeros((2, pad)), np.zeros((2, trim))), 1
            )
            mix_waves = []
            i = 0
            while i < n_sample + pad:
                waves = np.array(mix_p[:, i : i + model.chunk_size])
                mix_waves.append(waves)
                i += gen_size
            
            mix_waves = np.asarray(mix_waves, dtype=np.float32)

            _ort = self.model
            spek = model.stft(mix_waves)
            if self.args["denoise"]:
                spec_pred = (
                    -_ort.run(None, {"input": -spek})[0] * 0.5
                    + _ort.run(None, {"input": spek})[0] * 0.5
                )
            else:
                spec_pred = _ort.run(None, {"input": spek})[0]
            tar_waves = model.istft(spec_pred)
            tar_signal = (
                tar_waves[:, :, trim:-trim]
                .swapaxes(0, 1)
                .reshape(2, -1)[:, :-pad]
            )

            start = 0 if mix == 0 else margin_size
            end = None if mix == list(mixes.keys())[::-1][0] else -margin_size

            if margin_size == 0:
                end = None

            sources.append(tar_signal[:, start:end])

            progress_bar.update(1)

            chunked_sources.append(sources)
        _sources = np.concatenate(chunked_sources, axis=-1)
        
        progress_bar.close()
        return _sources

    def predict(self, file_path):
      
        mix, rate = librosa.load(file_path, mono=False, sr=44100)
        
        if mix.ndim == 1:
            mix = np.asfortranarray([mix, mix])
        
        mix = mix.T
        sources = self.demix(mix.T)
        opt = sources[0].T
        
        return (mix - opt, opt, rate)

def main():
    parser = ArgumentParser()
    
    parser.add_argument("files", nargs="+", type=str, default=[], help="Source audio path")
    parser.add_argument("-m", "--model_path", type=str, help="MDX Net ONNX Model path")
    parser.add_argument("-d", "--no-denoise", dest="denoise", action="store_false", default=True, help="Disable denoising")
    parser.add_argument("-M", "--margin", type=int, default=44100, help="Margin")
    parser.add_argument("-c", "--chunks", type=int, default=15, help="Chunk size")
    parser.add_argument("-F", "--n_fft", type=int, default=6144)
    parser.add_argument("-t", "--dim_t", type=int, default=8)
    parser.add_argument("-f", "--dim_f", type=int, default=2048)
    args = parser.parse_args()
    
    dict_args = vars(args)
    
    
    for file_path in args.files:  
      predictor = Predictor(args=dict_args)
      vocals, no_vocals, sampling_rate = predictor.predict(file_path)
      sf.write(os.path.join(file_path+"_no_vocals.wav"), no_vocals, sampling_rate)
      sf.write(os.path.join(file_path+"_vocals.wav"), vocals, sampling_rate)
  
if __name__ == "__main__":
    main()
