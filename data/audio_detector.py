import numpy as np
import collections
import threading
from mediapipe.tasks import python
from mediapipe.tasks.python import audio
from mediapipe.tasks.python.components import containers
from mediapipe.tasks.python.audio import audio_classifier
import mediapipe as mp
import time
import logging


class AudioDetector:
  def __init__(self, model_path, sample_rate=16000, buffer_duration=1.0):
    self.model_path = model_path
    self.sample_rate = sample_rate
    self.buffer_size = int(buffer_duration * sample_rate)
    self.sources = {}  # Dict pour stocker les buffers et callbacks par source
    self.source_ids = {}  # Dict pour mapper les noms de source aux IDs numériques
    self.next_source_id = 1  # Commencer à 1 pour éviter les problèmes avec 0
    self.classifier = None
    self.running = False
    self.lock = threading.Lock()
    # Dict pour stocker le dernier temps de détection par source
    self.last_detection_time = {}
    self.last_timestamp_ms = {}  # Dict pour stocker le dernier timestamp par source
    self.last_stats_log_time = {}
    self.start_time_ms = None
    self.current_source_id = None  # Pour suivre la source actuelle dans le callback
    self.max_results = 5
    self.score_threshold = 0.3
    self.label_display_threshold = 0.5
    self.result_log_threshold = 0.55
    self.finger_snapping_penalty = 0.20
    self.direct_clap_label_threshold = 0.25
    self.slap_smack_weight = 0.60
    self.min_detection_interval_ms = 350
    self.non_clap_label_thresholds = {
        "Speech": 0.35,
        "Whistling": 0.22,
        "Computer keyboard": 0.20,
        "Typewriter": 0.12,
    }
    self.clap_labels = {"Hands", "Clapping", "Finger snapping"}
    self.allowed_non_clap_labels = {
        "Speech",
        "Whistling",
        "Computer keyboard",
        "Typewriter"
    }

  def _normalize_label(self, label_name):
    if label_name == "Typewriter":
      return "Computer keyboard"
    return label_name

  def initialize(self, max_results=5, score_threshold=0.3):
    """Initialise le classificateur audio"""
    try:
      self.max_results = max_results
      self.score_threshold = score_threshold
      base_options = python.BaseOptions(model_asset_path=self.model_path)

      # Créer un seul classificateur en mode stream
      options = audio.AudioClassifierOptions(
          base_options=base_options,
          running_mode=audio.RunningMode.AUDIO_STREAM,
          max_results=max_results,
          score_threshold=score_threshold,
          result_callback=self._handle_result
      )
      self.classifier = audio.AudioClassifier.create_from_options(options)
      self.running = True
      logging.info(
          f"Classificateur audio initialisé avec succès (sample_rate: {self.sample_rate}Hz)")
      logging.info(
          f"Options du classificateur: max_results={max_results}, score_threshold={score_threshold}")
    except Exception as e:
      logging.error(
          f"Erreur lors de l'initialisation du classificateur: {str(e)}")
      import traceback
      logging.error(traceback.format_exc())
      raise

  def add_source(self, source_id, detection_callback=None, labels_callback=None):
    """Ajoute une nouvelle source audio avec ses callbacks"""
    with self.lock:
      # Attribuer un ID numérique à la source
      numeric_id = self.next_source_id
      self.next_source_id += 1
      self.source_ids[source_id] = numeric_id

      self.sources[source_id] = {
          'buffer': collections.deque(maxlen=self.buffer_size),
          'detection_callback': detection_callback,
          'labels_callback': labels_callback,
          'numeric_id': numeric_id
      }
      self.last_detection_time[source_id] = 0
      self.last_timestamp_ms[source_id] = 0
      self.last_stats_log_time[source_id] = 0
      logging.info(
          f"Source audio ajoutée: {source_id} (ID interne: {numeric_id})")

  def remove_source(self, source_id):
    """Supprime une source audio"""
    with self.lock:
      if source_id in self.sources:
        numeric_id = self.sources[source_id]['numeric_id']
        del self.source_ids[source_id]
        del self.sources[source_id]
        del self.last_detection_time[source_id]
        del self.last_timestamp_ms[source_id]
        del self.last_stats_log_time[source_id]
        logging.info(
            f"Source audio supprimée: {source_id} (ID interne: {numeric_id})")

  def _handle_result(self, result, timestamp):
    """Gère les résultats de classification"""
    try:
      if not result or not result.classifications or not self.current_source_id:
        return

      classification = result.classifications[0]
      source_id = self.current_source_id

      top_categories = sorted(
          classification.categories,
          key=lambda x: x.score,
          reverse=True
      )[:3]

      # Calculer le score pour la détection de clap
      score_sum = sum(
          category.score
          for category in classification.categories
          if category.category_name in self.clap_labels - {"Finger snapping"}
      )
      score_sum += sum(
          category.score * self.slap_smack_weight
          for category in classification.categories
          if category.category_name == "Slap, smack"
      )
      finger_snapping_score = sum(
          category.score
          for category in classification.categories
          if category.category_name == "Finger snapping"
      )
      score_sum -= finger_snapping_score * self.finger_snapping_penalty

      direct_clap_score = max(
          (
              category.score
              for category in classification.categories
              if category.category_name in {"Clapping", "Hands"}
          ),
          default=0.0
      )

      should_log_results = False
      if top_categories:
        has_clap_candidate = any(
            category.category_name in self.clap_labels and category.score > 0.1
            for category in top_categories
        )
        has_allowed_non_clap = any(
            category.category_name in self.allowed_non_clap_labels
            and category.score > self.non_clap_label_thresholds.get(
                category.category_name, 0.35
            )
            for category in top_categories
        )
        should_log_results = (
            has_clap_candidate
            or score_sum > 0.1
            or direct_clap_score > 0.1
            or has_allowed_non_clap
        )

      if should_log_results:
        logging.debug(f"Résultats bruts pour source {source_id}:")
        for category in top_categories:
          logging.debug(f"  - {category.category_name}: {category.score}")

      # Log du score calculé
      if score_sum > 0.1 or direct_clap_score > 0.1:
        logging.debug(
            f"Score de clap calculé pour source {source_id}: {score_sum} (direct={direct_clap_score}, snap={finger_snapping_score})")

      labels_data = [
          {"label": self._normalize_label(label.category_name), "score": float(label.score)}
          for label in top_categories
          if (
              (
                  label.score > self.label_display_threshold
                  and label.category_name in self.clap_labels
              )
              or (
                  label.category_name in self.allowed_non_clap_labels
                  and label.score > self.non_clap_label_thresholds.get(
                      label.category_name, 0.35
                  )
              )
          )
      ]

      if labels_data or score_sum > 0.1 or direct_clap_score > 0.1:
        logging.debug(f"Labels détectés pour source {source_id}: {labels_data}")

      # Envoyer les labels si un callback est défini
      if self.sources[source_id]['labels_callback'] and labels_data:
        try:
          self.sources[source_id]['labels_callback'](labels_data)
        except Exception as e:
          logging.error(
              f"Erreur dans le callback des labels pour source {source_id}: {str(e)}")

      # Vérifier si on a détecté un clap
      event_time = timestamp / 1000.0
      clap_detected = (
          score_sum > self.score_threshold
          or direct_clap_score > self.direct_clap_label_threshold
      )
      if clap_detected and (
          timestamp - self.last_detection_time.get(source_id, 0)
      ) > self.min_detection_interval_ms:
        if self.sources[source_id]['detection_callback']:
          try:
            self.sources[source_id]['detection_callback']({
                'timestamp': event_time,
                'score': float(max(score_sum, direct_clap_score)),
                'source_id': source_id
            })
          except Exception as e:
            logging.error(
                f"Erreur dans le callback de détection pour source {source_id}: {str(e)}")
        self.last_detection_time[source_id] = timestamp

    except Exception as e:
      logging.error(f"Erreur dans le traitement du résultat: {str(e)}")
      import traceback
      logging.error(traceback.format_exc())

  def process_audio(self, audio_data, source_id):
    """Traite les données audio pour une source spécifique"""
    try:
      if source_id not in self.sources:
        logging.warning(f"Source inconnue: {source_id}")
        return

      # Vérifier si le classificateur est actif
      if not self.running:
        logging.warning("Le classificateur n'est pas actif, démarrage...")
        self.start()
        if not self.running:
          logging.error("Impossible de démarrer le classificateur")
          return

      # Rééchantillonnage si nécessaire
      if len(audio_data) > self.buffer_size:
        resampled_data = audio_data[::3]
        audio_data = resampled_data

      # S'assurer que les données sont en float32
      if audio_data.dtype != np.float32:
        audio_data = audio_data.astype(np.float32)

      # Log des statistiques audio
      if len(audio_data) > 0:
        now_ms = int(time.monotonic() * 1000)
        last_log_ms = self.last_stats_log_time.get(source_id, 0)
        should_log_stats = (
            now_ms - last_log_ms > 1000
            or np.max(np.abs(audio_data)) > 0.1
            or np.std(audio_data) > 0.05
        )
        if should_log_stats:
          self.last_stats_log_time[source_id] = now_ms
          logging.debug(
              f"Audio stats (source {source_id}) - min: {np.min(audio_data):.4f}, max: {np.max(audio_data):.4f}, mean: {np.mean(audio_data):.4f}, std: {np.std(audio_data):.4f}")

      # Ajouter les nouvelles données au buffer de la source
      self.sources[source_id]['buffer'].extend(audio_data)

      # Traiter avec le classificateur
      if self.running and self.classifier and self.start_time_ms is not None:
        block_size = 1600
        buffer_array = np.array(list(self.sources[source_id]['buffer']))

        blocks_processed = 0
        while len(buffer_array) >= block_size:
          block = buffer_array[:block_size]
          buffer_array = buffer_array[block_size:]
          blocks_processed += 1

          # Le timestamp doit rester cohérent avec les échantillons réellement
          # envoyés au classificateur en mode stream.
          block_duration_ms = int((block_size / self.sample_rate) * 1000)
          next_timestamp = self.last_timestamp_ms.get(
              source_id, self.start_time_ms
          ) + block_duration_ms
          self.last_timestamp_ms[source_id] = next_timestamp

          # Vérifier les statistiques du bloc avant classification
          block_max = np.max(np.abs(block))
          block_std = np.std(block)
          if block_max > 0.1:
            logging.debug(
                f"Classification d'un bloc audio (source {source_id}) - amplitude max: {block_max:.4f}")

          audio_data_container = containers.AudioData.create_from_array(
              block,
              self.sample_rate
          )

          # Définir la source actuelle pour le callback
          self.current_source_id = source_id

          # Log avant la classification
          if block_max > 0.1:
            logging.debug(
                f"Envoi au classificateur - source: {source_id}, timestamp: {next_timestamp}")

          # Classifier le bloc
          try:
            self.classifier.classify_async(
                audio_data_container, next_timestamp)
          except Exception as e:
            logging.error(f"Erreur lors de la classification: {str(e)}")

        if blocks_processed > 0:
          logging.debug(f"Blocs traités pour {source_id}: {blocks_processed}")

        # Mettre à jour le buffer avec les données restantes
        self.sources[source_id]['buffer'].clear()
        if len(buffer_array) > 0:
          self.sources[source_id]['buffer'].extend(buffer_array)

    except Exception as e:
      logging.error(f"Erreur dans le traitement audio: {e}")
      import traceback
      logging.error(traceback.format_exc())

  def start(self):
    """Démarre la détection"""
    if not self.classifier:
      self.initialize(
          max_results=self.max_results,
          score_threshold=self.score_threshold
      )

    # Réinitialiser les timestamps et les compteurs d'échantillons
    self.start_time_ms = int(time.monotonic() * 1000)
    for source_id in self.sources:
      self.last_timestamp_ms[source_id] = self.start_time_ms

    # Démarrer le task runner de MediaPipe
    if self.classifier:
      try:
        # Créer un conteneur audio vide pour démarrer le stream
        empty_data = np.zeros(1600, dtype=np.float32)
        audio_data = containers.AudioData.create_from_array(
            empty_data,
            self.sample_rate
        )
        # Démarrer le stream avec le timestamp initial
        self.classifier.classify_async(audio_data, self.start_time_ms)
        self.running = True
        logging.info("Task runner MediaPipe démarré avec succès")
      except Exception as e:
        logging.error(f"Erreur lors du démarrage du task runner: {e}")
        return False

    self.running = True
    return True

  def stop(self):
    """Arrête le classificateur"""
    self.running = False
    if self.classifier:
      try:
        self.classifier.close()
        self.classifier = None
        logging.info("Classificateur audio arrêté")
      except Exception as e:
        logging.error(f"Erreur lors de l'arrêt du classificateur: {e}")

  def __del__(self):
    """Destructeur pour s'assurer que les classificateurs sont bien arrêtés"""
    self.stop()
