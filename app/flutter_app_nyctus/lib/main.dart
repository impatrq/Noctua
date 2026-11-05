import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import 'services/api_service.dart';
import 'services/local_historial_service.dart';

const String kUrlPaginaWeb =
    'https://sites.google.com/view/proyecto-nyctus/introducci%C3%B3n-del-proyecto';

void main() {
  runApp(const NereasApp());
}

const Duration kTiempoExpiracionAnalisis =
    Duration(minutes: 20);

class NereasApp extends StatelessWidget {
  const NereasApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Nyctus',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF101820),
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const MainScreen(),
    );
  }
}

// ==========================================================
// PANTALLA PRINCIPAL
// ==========================================================

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int paginaActual = 0;

  final paginas = const [
    HomeScreen(),
    HistoryScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: paginaActual,
        children: paginas,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: paginaActual,
        onDestinationSelected: (index) {
          setState(() {
            paginaActual = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Inicio',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_outlined),
            selectedIcon: Icon(Icons.history),
            label: 'Historial',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Ajustes',
          ),
        ],
      ),
    );
  }
}

// ==========================================================
// INICIO
// ==========================================================

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int ganado = 0;

  bool cargando = true;
  bool solicitandoAnalisis = false;
  bool _consultandoEstado = false;

  String mensajeEstado = '';
  String estadoActual = 'inactivo';

  int progreso = 0;
  bool workerOnline = false;

  DateTime? fechaUltimoAnalisis;
  DateTime? fechaInicioAnalisis;

  Timer? _timerExpiracion;
  Timer? _timerEstado;

  // Estados que representan un análisis REAL en curso.
  // Que el worker esté conectado no significa que haya
  // un análisis activo.
  static const Set<String> _estadosActivos = {
    'pendiente',
    'grabando',
    'subiendo',
    'esperando_ia',
    'descargando',
    'procesando',
    'comprimiendo',
    'subiendo_resultado',
  };

  bool get analisisEnCurso {
    return _estadosActivos.contains(estadoActual) ||
        solicitandoAnalisis;
  }

  @override
  void initState() {
    super.initState();

    cargarDatos();
    consultarEstado();

    // Consultar el servidor cada 3 segundos.
    _timerEstado = Timer.periodic(
      const Duration(seconds: 3),
      (_) {
        consultarEstado();
      },
    );

    // Actualizar el cronómetro y la expiración visual.
    _timerExpiracion = Timer.periodic(
      const Duration(seconds: 1),
      (_) {
        if (mounted) {
          setState(() {});
        }
      },
    );
  }

  @override
  void dispose() {
    _timerEstado?.cancel();
    _timerExpiracion?.cancel();
    super.dispose();
  }

  // ========================================================
  // CARGAR ÚLTIMO ANÁLISIS
  // ========================================================

  Future<void> cargarDatos() async {
    if (!mounted) return;

    try {
      final datos = await ApiService.obtenerAnalisis();

      if (!mounted) return;

      setState(() {
        ganado = int.tryParse(
              datos['ganado']?.toString() ?? '0',
            ) ??
            0;

        fechaUltimoAnalisis = DateTime.tryParse(
          datos['fecha']?.toString() ?? '',
        );

        cargando = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        cargando = false;
      });

      debugPrint('Error al cargar análisis: $e');
    }
  }

  // ========================================================
  // CONSULTAR ESTADO DEL ANÁLISIS Y CONEXIÓN DE YOLO
  // ========================================================

  Future<void> consultarEstado() async {
    if (!mounted || _consultandoEstado) return;

    _consultandoEstado = true;

    try {
      final datos = await ApiService.obtenerEstado();

      if (!mounted) return;

      final nuevoEstado =
          (datos['estado']?.toString() ?? 'inactivo')
              .toLowerCase()
              .trim();

      final nuevaFechaInicio = DateTime.tryParse(
        datos['fecha_inicio']?.toString() ?? '',
      );

      final nuevoProgreso = int.tryParse(
            datos['progreso']?.toString() ?? '0',
          ) ??
          0;

      final nuevoMensaje =
          datos['mensaje']?.toString() ?? '';

      final nuevoWorkerOnline =
          datos['worker_online'] == true;

      // Detectar si acaba de completarse el análisis.
      // Así evitamos descargar los datos repetidamente
      // cada vez que se consulta el servidor.
      final acabaDeCompletar =
          nuevoEstado == 'completado' &&
          estadoActual != 'completado';

      setState(() {
        estadoActual = nuevoEstado;

        progreso = nuevoProgreso.clamp(0, 100).toInt();

        mensajeEstado = nuevoMensaje;
        workerOnline = nuevoWorkerOnline;
        fechaInicioAnalisis = nuevaFechaInicio;

        // El botón se bloquea únicamente cuando el servidor
        // informa que existe un análisis en curso.
        solicitandoAnalisis =
            _estadosActivos.contains(nuevoEstado);

        if (nuevoEstado == 'completado') {
          progreso = 100;
          solicitandoAnalisis = false;
        }

        if (nuevoEstado == 'error' ||
            nuevoEstado == 'inactivo') {
          solicitandoAnalisis = false;
        }
      });

      // Actualizar el contador solamente cuando termina.
      if (acabaDeCompletar) {
        await cargarDatos();
      }
    } catch (e) {
      debugPrint('Error consultando estado: $e');
    } finally {
      _consultandoEstado = false;
    }
  }

  // ========================================================
  // SOLICITAR NUEVO ANÁLISIS
  // ========================================================

  Future<void> solicitarNuevoAnalisis() async {
    if (analisisEnCurso) return;

    setState(() {
      solicitandoAnalisis = true;
      estadoActual = 'pendiente';
      progreso = 0;
      mensajeEstado = 'Enviando solicitud...';
      fechaInicioAnalisis = DateTime.now();
    });

    try {
      await ApiService.nuevoAnalisis();

      if (!mounted) return;

      setState(() {
        estadoActual = 'pendiente';
        solicitandoAnalisis = true;
        mensajeEstado =
            'Solicitud recibida. Esperando a la Raspberry Pi.';
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Análisis solicitado correctamente.',
          ),
          duration: Duration(seconds: 3),
        ),
      );

      await consultarEstado();
    } catch (e) {
      if (!mounted) return;

      // Si el servidor informa que ya existe un análisis,
      // consultamos su estado antes de liberar el botón.
      await consultarEstado();

      if (!mounted) return;

      if (!analisisEnCurso) {
        setState(() {
          solicitandoAnalisis = false;
        });
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'No se pudo solicitar el análisis: $e',
          ),
          duration: const Duration(seconds: 4),
        ),
      );

      debugPrint('Error solicitando análisis: $e');
    }
  }

  // ========================================================
  // EXPIRACIÓN DEL ÚLTIMO ANÁLISIS
  // ========================================================

  bool get analisisVencido {
    if (fechaUltimoAnalisis == null) return true;

    return DateTime.now().difference(fechaUltimoAnalisis!) >
        kTiempoExpiracionAnalisis;
  }

  // ========================================================
  // TIEMPO TRANSCURRIDO DEL ANÁLISIS
  // ========================================================

  String get tiempoTranscurrido {
    if (fechaInicioAnalisis == null) return '00:00';

    final diferencia =
        DateTime.now().difference(fechaInicioAnalisis!);

    final segundos = diferencia.inSeconds;

    final horas = segundos ~/ 3600;
    final minutos = (segundos % 3600) ~/ 60;
    final restoSegundos = segundos % 60;

    if (horas > 0) {
      return '${horas.toString().padLeft(2, '0')}:'
          '${minutos.toString().padLeft(2, '0')}:'
          '${restoSegundos.toString().padLeft(2, '0')}';
    }

    return '${minutos.toString().padLeft(2, '0')}:'
        '${restoSegundos.toString().padLeft(2, '0')}';
  }

  // ========================================================
  // NOMBRE AMIGABLE DEL ESTADO
  // ========================================================

  String get nombreEstado {
    switch (estadoActual) {
      case 'pendiente':
        return 'Solicitud pendiente';

      case 'grabando':
        return 'Grabando video';

      case 'subiendo':
        return 'Subiendo video';

      case 'esperando_ia':
        return 'Esperando computadora';

      case 'descargando':
        return 'Descargando video';

      case 'procesando':
        return 'Procesando con inteligencia artificial';

      case 'comprimiendo':
        return 'Comprimiendo video';

      case 'subiendo_resultado':
        return 'Subiendo resultado';

      case 'completado':
        return 'Análisis completado';

      case 'error':
        return 'Error en el análisis';

      default:
        return 'Sistema listo';
    }
  }

  // ========================================================
  // INTERFAZ
  // ========================================================

  @override
  Widget build(BuildContext context) {
    final mostrarVencido = !cargando && analisisVencido;

    final ganadoAMostrar =
        mostrarVencido ? 0 : ganado;

    return SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const SizedBox(height: 20),

              // LOGO
              ClipOval(
                child: Image.asset(
                  'assets/logo.jpg',
                  width: 180,
                  height: 180,
                  fit: BoxFit.cover,
                ),
              ),

              const SizedBox(height: 30),

              // CONTADOR DE GANADO
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(30),
                decoration: BoxDecoration(
                  color: const Color(0xFF172635),
                  borderRadius: BorderRadius.circular(25),
                ),
                child: Column(
                  children: [
                    const Text(
                      'Ganado detectado',
                      style: TextStyle(
                        fontSize: 18,
                        color: Colors.grey,
                      ),
                    ),

                    const SizedBox(height: 10),

                    cargando
                        ? const CircularProgressIndicator()
                        : Text(
                            '$ganadoAMostrar',
                            style: const TextStyle(
                              fontSize: 64,
                              fontWeight: FontWeight.bold,
                              color: Colors.blue,
                            ),
                          ),

                    const Text(
                      'cabezas',
                      style: TextStyle(fontSize: 18),
                    ),

                    const SizedBox(height: 15),

                    Text(
                      mostrarVencido
                          ? 'Sin análisis reciente'
                          : (mensajeEstado.isEmpty
                              ? 'Datos obtenidos del servidor'
                              : mensajeEstado),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.grey,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // ESTADO DE CONEXIÓN DE LA COMPUTADORA
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 14,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFF172635),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: Row(
                  children: [
                    Icon(
                      workerOnline
                          ? Icons.computer
                          : Icons.computer_outlined,
                      color: workerOnline
                          ? Colors.green
                          : Colors.orange,
                    ),

                    const SizedBox(width: 12),

                    Expanded(
                      child: Column(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Computadora de inteligencia artificial',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                            ),
                          ),

                          const SizedBox(height: 3),

                          Text(
                            workerOnline
                                ? 'Conectada y disponible'
                                : 'Desconectada o sin comunicación',
                            style: TextStyle(
                              fontSize: 12,
                              color: workerOnline
                                  ? Colors.green
                                  : Colors.orange,
                            ),
                          ),
                        ],
                      ),
                    ),

                    Icon(
                      Icons.circle,
                      size: 11,
                      color: workerOnline
                          ? Colors.green
                          : Colors.orange,
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 15),

              // PANEL DE PROGRESO
              if (analisisEnCurso ||
                  estadoActual == 'completado' ||
                  estadoActual == 'error')
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF172635),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.analytics_outlined,
                            color: Colors.blue,
                          ),

                          const SizedBox(width: 10),

                          const Expanded(
                            child: Text(
                              'Estado del análisis',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),

                          Text(
                            '$progreso%',
                            style: const TextStyle(
                              color: Colors.blue,
                              fontWeight: FontWeight.bold,
                              fontSize: 17,
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 15),

                      Text(
                        nombreEstado,
                        style: TextStyle(
                          color: estadoActual == 'error'
                              ? Colors.redAccent
                              : estadoActual == 'completado'
                                  ? Colors.green
                                  : Colors.white,
                          fontSize: 14,
                        ),
                      ),

                      const SizedBox(height: 12),

                      LinearProgressIndicator(
                        value: progreso <= 0
                          ? 0.0
                          : progreso >= 100
                              ? 1.0
                              : math.log(1 + 9 * (progreso / 100)) / math.log(10),
                        minHeight: 9,
                        borderRadius: BorderRadius.circular(10),
                        backgroundColor: Colors.grey.shade800,
                        color: estadoActual == 'error'
                            ? Colors.redAccent
                            : estadoActual == 'completado'
                                ? Colors.green
                                : Colors.blue,
                      ),

                      const SizedBox(height: 15),

                      Row(
                        children: [
                          const Icon(
                            Icons.timer_outlined,
                            size: 18,
                            color: Colors.grey,
                          ),

                          const SizedBox(width: 8),

                          const Text(
                            'Tiempo transcurrido:',
                            style: TextStyle(
                              color: Colors.grey,
                              fontSize: 13,
                            ),
                          ),

                          const Spacer(),

                          Text(
                            tiempoTranscurrido,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),

                      if (estadoActual == 'error' &&
                          mensajeEstado.isNotEmpty) ...[
                        const SizedBox(height: 12),

                        Text(
                          mensajeEstado,
                          style: const TextStyle(
                            color: Colors.redAccent,
                            fontSize: 12,
                          ),
                        ),
                      ],

                      if (analisisEnCurso && !workerOnline) ...[
                        const SizedBox(height: 12),

                        const Text(
                          'La computadora de IA no está enviando señales. '
                          'El análisis puede quedar esperando hasta que se conecte.',
                          style: TextStyle(
                            color: Colors.orange,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),

              const SizedBox(height: 20),

              // ACTUALIZAR DATOS
              SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton.icon(
                  onPressed: cargando ? null : cargarDatos,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Actualizar datos'),
                ),
              ),

              const SizedBox(height: 12),

              // NUEVO ANÁLISIS
              SizedBox(
                width: double.infinity,
                height: 55,
                child: OutlinedButton.icon(
                  onPressed: analisisEnCurso
                      ? null
                      : solicitarNuevoAnalisis,

                  icon: analisisEnCurso
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(
                          Icons.video_camera_back,
                        ),

                  label: Text(
                    analisisEnCurso
                        ? 'Análisis en curso...'
                        : 'Nuevo análisis',
                  ),
                ),
              ),

              const SizedBox(height: 15),
            ],
          ),
        ),
      ),
    );
  }
}

// ==========================================================
// HISTORIAL
// ==========================================================

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() =>
      _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> videos = [];

  bool cargando = true;

  Timer? _timerAutoRefresh;

  @override
  void initState() {
    super.initState();

    _cargarCacheYSincronizar();

    _timerAutoRefresh = Timer.periodic(
      const Duration(seconds: 10),
      (_) => cargarHistorial(
        mostrarCargando: false,
      ),
    );
  }

  @override
  void dispose() {
    _timerAutoRefresh?.cancel();
    super.dispose();
  }

  // ========================================================
  // MOSTRAR CACHE LOCAL Y DESPUÉS SINCRONIZAR CON RENDER
  // ========================================================

  Future<void> _cargarCacheYSincronizar() async {
    final cache =
        await LocalHistorialService.instancia.cargarLocal();

    if (mounted && cache.isNotEmpty) {
      setState(() {
        videos = cache;
        cargando = false;
      });
    }

    await cargarHistorial(
      mostrarCargando: cache.isEmpty,
    );
  }

  // ========================================================
  // CARGAR / SINCRONIZAR HISTORIAL
  // ========================================================

  Future<void> cargarHistorial({
    bool mostrarCargando = true,
  }) async {
    if (!mounted) return;

    if (mostrarCargando) {
      setState(() {
        cargando = true;
      });
    }

    try {
      final datos =
          await LocalHistorialService.instancia.sincronizar();

      if (!mounted) return;

      setState(() {
        videos = datos;
        cargando = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        cargando = false;
      });

      debugPrint('Error al cargar historial: $e');
    }
  }

  // ========================================================
  // FORMATEAR DURACIÓN
  // ========================================================

  String _formatearDuracion(dynamic valor) {
    final segundos = (valor is num)
        ? valor.toDouble()
        : double.tryParse(valor.toString()) ?? 0.0;

    return '${segundos.toStringAsFixed(1)} s';
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 20),

            const Text(
              'Historial',
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 20),

            Expanded(
              child: cargando
                  ? const Center(
                      child: CircularProgressIndicator(),
                    )
                  : videos.isEmpty
                      ? const Center(
                          child: Text(
                            'Todavía no hay análisis registrados.',
                            style: TextStyle(
                              color: Colors.grey,
                            ),
                          ),
                        )
                      : RefreshIndicator(
                          onRefresh: cargarHistorial,
                          child: ListView.builder(
                            itemCount: videos.length,
                            itemBuilder: (context, index) {
                              final video = videos[index];

                              final String? nombreArchivo =
                                  video['video'] as String?;

                              return Card(
                                margin: const EdgeInsets.only(
                                  bottom: 12,
                                ),
                                child: ListTile(
                                  leading: Container(
                                    width: 60,
                                    height: 60,
                                    decoration: BoxDecoration(
                                      color: Colors.grey.shade800,
                                      borderRadius:
                                          BorderRadius.circular(10),
                                    ),
                                    child: const Icon(
                                      Icons.play_arrow,
                                      color: Colors.blue,
                                    ),
                                  ),

                                  title: Text(
                                    video['fecha']?.toString() ??
                                        'Sin fecha',
                                  ),

                                  subtitle: Text(
                                    '🐄 ${video['ganado'] ?? 0} cabezas\n'
                                    '👤 ${video['personas'] ?? 0} personas\n'
                                    '⏱ ${_formatearDuracion(video['duracion'] ?? 0)}',
                                  ),

                                  isThreeLine: true,

                                  trailing: const Icon(
                                    Icons.arrow_forward_ios,
                                    size: 16,
                                  ),

                                  onTap: () {
                                    // Reproducir primero la copia local.
                                    final archivoLocal =
                                        video['archivo_local'] as String?;

                                    if (archivoLocal != null) {
                                      Navigator.of(context).push(
                                        MaterialPageRoute(
                                          builder: (_) =>
                                              VideoPlayerScreen(
                                            rutaLocal: archivoLocal,
                                          ),
                                        ),
                                      );

                                      return;
                                    }

                                    if (nombreArchivo == null ||
                                        nombreArchivo.isEmpty) {
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
                                        const SnackBar(
                                          content: Text(
                                            'Este análisis no tiene '
                                            'video procesado.',
                                          ),
                                        ),
                                      );

                                      return;
                                    }

                                    final videoUrl =
                                        '${ApiService.baseUrl}/video-analisis/$nombreArchivo';

                                    Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) =>
                                            VideoPlayerScreen(
                                          videoUrl: videoUrl,
                                        ),
                                      ),
                                    );
                                  },
                                ),
                              );
                            },
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================================
// REPRODUCTOR DE VIDEO
// ==========================================================

class VideoPlayerScreen extends StatefulWidget {
  final String? videoUrl;
  final String? rutaLocal;

  const VideoPlayerScreen({
    super.key,
    this.videoUrl,
    this.rutaLocal,
  }) : assert(
          videoUrl != null || rutaLocal != null,
          'Hay que pasar videoUrl o rutaLocal',
        );

  @override
  State<VideoPlayerScreen> createState() =>
      _VideoPlayerScreenState();
}

class _VideoPlayerScreenState
    extends State<VideoPlayerScreen> {
  late final VideoPlayerController _controller;

  bool _error = false;

  @override
  void initState() {
    super.initState();

    _controller = widget.rutaLocal != null
        ? VideoPlayerController.file(
            File(widget.rutaLocal!),
          )
        : VideoPlayerController.networkUrl(
            Uri.parse(widget.videoUrl!),
          );

    _controller.initialize().then((_) {
      if (!mounted) return;

      setState(() {});

      _controller.play();
    }).catchError((_) {
      if (!mounted) return;

      setState(() {
        _error = true;
      });
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Video del análisis'),
      ),

      body: Center(
        child: _error
            ? const Text(
                'No se pudo cargar el video.',
                style: TextStyle(
                  color: Colors.grey,
                ),
              )
            : _controller.value.isInitialized
                ? AspectRatio(
                    aspectRatio:
                        _controller.value.aspectRatio,
                    child: Stack(
                      alignment: Alignment.bottomCenter,
                      children: [
                        VideoPlayer(_controller),

                        VideoProgressIndicator(
                          _controller,
                          allowScrubbing: true,
                        ),
                      ],
                    ),
                  )
                : const CircularProgressIndicator(),
      ),

      floatingActionButton:
          _controller.value.isInitialized
              ? FloatingActionButton(
                  onPressed: () {
                    setState(() {
                      _controller.value.isPlaying
                          ? _controller.pause()
                          : _controller.play();
                    });
                  },
                  child: Icon(
                    _controller.value.isPlaying
                        ? Icons.pause
                        : Icons.play_arrow,
                  ),
                )
              : null,
    );
  }
}

// ==========================================================
// AJUSTES
// ==========================================================

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const SizedBox(height: 20),

          const Text(
            'Ajustes',
            style: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.bold,
            ),
          ),

          const SizedBox(height: 25),

          SwitchListTile(
            title: const Text('Notificaciones'),
            subtitle: const Text(
              'Recibir avisos de nuevos análisis',
            ),
            value: true,
            onChanged: (value) {},
          ),

          const Divider(),

          ListTile(
            leading: const Icon(Icons.cloud),
            title: const Text('Sincronización'),
            subtitle: const Text('Conectado'),
            onTap: () {},
          ),

          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Acerca de Nyctus'),
            onTap: () async {
              final uri = Uri.parse(kUrlPaginaWeb);

              final pudoAbrir = await launchUrl(
                uri,
                mode: LaunchMode.externalApplication,
              );

              if (!pudoAbrir && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'No se pudo abrir la página.',
                    ),
                  ),
                );
              }
            },
          ),
        ],
      ),
    );
  }
}