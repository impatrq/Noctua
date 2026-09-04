import 'package:flutter/material.dart';
import 'services/api_service.dart';

void main() {
  runApp(const NereasApp());
}

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

// --------------------------------------------------
// INICIO
// --------------------------------------------------

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int ganado = 0;
  bool cargando = true;

  @override
  void initState() {
    super.initState();
    cargarDatos();
  }

  Future<void> cargarDatos() async {
    setState(() {
      cargando = true;
    });

    try {
      final datos = await ApiService.obtenerAnalisis();

      if (!mounted) return;
      setState(() {
        ganado = datos['ganado'];
        cargando = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        cargando = false;
      });
      debugPrint("Error al conectar con la API: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const SizedBox(height: 20),

            // LOGO DE NYCTUS
            ClipOval(
              child: Image.asset(
                'assets/logo.jpg',
                width: 180,
                height: 180,
                fit: BoxFit.cover,
              ),
            ),

            const SizedBox(height: 30),

            // CONTADOR
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
                          '$ganado',
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

                  const Text(
                    'Último análisis: Hoy - 08:45',
                    style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 25),

            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton.icon(
                onPressed: cargarDatos,
                icon: const Icon(Icons.refresh),
                label: const Text('Actualizar datos'),
              ),
            ),

            const SizedBox(height: 12),

            SizedBox(
              width: double.infinity,
              height: 55,
              child: OutlinedButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.video_camera_back),
                label: const Text('Nuevo análisis'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// --------------------------------------------------
// HISTORIAL
// --------------------------------------------------

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> videos = [];
  bool cargando = true;

  @override
  void initState() {
    super.initState();
    cargarHistorial();
  }

  Future<void> cargarHistorial() async {
    setState(() {
      cargando = true;
    });

    try {
      final datos = await ApiService.obtenerHistorial();

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
      debugPrint("Error al cargar historial: $e");
    }
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
                  ? const Center(child: CircularProgressIndicator())
                  : videos.isEmpty
                      ? const Center(
                          child: Text(
                            'Todavía no hay análisis registrados.',
                            style: TextStyle(color: Colors.grey),
                          ),
                        )
                      : RefreshIndicator(
                          onRefresh: cargarHistorial,
                          child: ListView.builder(
                            itemCount: videos.length,
                            itemBuilder: (context, index) {
                              final video = videos[index];

                              return Card(
                                margin: const EdgeInsets.only(bottom: 12),
                                child: ListTile(
                                  leading: Container(
                                    width: 60,
                                    height: 60,
                                    decoration: BoxDecoration(
                                      color: Colors.grey.shade800,
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: const Icon(
                                      Icons.play_arrow,
                                      color: Colors.blue,
                                    ),
                                  ),

                                  title: Text(video['fecha'].toString()),

                                  subtitle: Text(
                                    '🐄 ${video['ganado']} cabezas\n'
                                    '👤 ${video['personas']} personas\n'
                                    '⏱ ${video['duracion']}',
                                  ),

                                  isThreeLine: true,

                                  trailing: const Icon(
                                    Icons.arrow_forward_ios,
                                    size: 16,
                                  ),

                                  onTap: () {
                                    // Más adelante abriremos
                                    // el detalle del análisis.
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

// --------------------------------------------------
// AJUSTES
// --------------------------------------------------

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
            onTap: () {},
          ),
        ],
      ),
    );
  }
}