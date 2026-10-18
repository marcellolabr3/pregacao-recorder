// fake_arecord - simulador do `arecord` (ALSA) para ambientes de teste
// (Windows/CI), onde nao existe captura real de audio.
//
// Comportamento:
//   arecord -l                 -> lista uma placa USB ficticia
//   arecord -q -D .. -f .. -r .. -c .. [-d N] -t raw -
//                              -> emite PCM 16-bit LE (senoide de 440 Hz,
//                                 amplitude 8000) em tempo real na stdout;
//                                 se houver -d N, encerra apos N segundos.
//
// Compilacao:  powershell -File scripts/devtools/build_fake_arecord.ps1
using System;
using System.IO;
using System.Threading;

static class FakeArecord
{
    static int rate = 44100;
    static int channels = 2;
    static int duration = 0;   // 0 = indefinido (roda ate ser morto)
    static bool listMode = false;

    static void Main(string[] args)
    {
        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "-l":
                    listMode = true;
                    break;
                case "-r":
                    rate = int.Parse(args[++i]);
                    break;
                case "-c":
                    channels = int.Parse(args[++i]);
                    break;
                case "-d":
                    duration = int.Parse(args[++i]);
                    break;
                case "-D":
                case "-f":
                case "-t":
                    i++;            // consome o valor
                    break;
                default:
                    break;          // -q, "-" e desconhecidos: ignora
            }
        }

        if (listMode)
        {
            Console.WriteLine("**** List of CAPTURE Hardware Devices ****");
            Console.WriteLine("card 1: FAKEUSB [Fake USB Audio], device 0: USB Audio [USB Audio]");
            Console.WriteLine("  Subdevices: 1/1");
            Console.WriteLine("  Subdevice #0: subdevice #0");
            return;
        }

        Stream stdout = Console.OpenStandardOutput();
        int chunkSamples = Math.Max(64, rate / 10);      // 0.1 s por escrita
        byte[] buf = new byte[chunkSamples * channels * 2];
        const double freq = 440.0;
        const short amp = 8000;
        double phase = 0;
        double step = 2 * Math.PI * freq / rate;
        DateTime start = DateTime.Now;

        try
        {
            while (true)
            {
                int idx = 0;
                for (int s = 0; s < chunkSamples; s++)
                {
                    short v = (short)(Math.Sin(phase) * amp);
                    phase += step;
                    if (phase > 2 * Math.PI) phase -= 2 * Math.PI;
                    for (int ch = 0; ch < channels; ch++)
                    {
                        buf[idx++] = (byte)(v & 0xFF);
                        buf[idx++] = (byte)((v >> 8) & 0xFF);
                    }
                }
                stdout.Write(buf, 0, buf.Length);
                stdout.Flush();

                if (duration > 0 &&
                    (DateTime.Now - start).TotalSeconds >= duration)
                    break;
                Thread.Sleep(100);                        // tempo real
            }
        }
        catch (IOException)
        {
            // leitor (Raspberry simulado) fechou o pipe: encerra limpo
        }
        catch (ObjectDisposedException)
        {
        }
    }
}
