# train.py

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
import joblib

class ModelTrainer:
    """Class to handle data loading, model training, and model saving."""
    
    def __init__(self, n_estimators=100, random_state=42, model_path="model.pkl"):
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model_path = model_path
        self.model = None
        self.X = None
        self.y = None

    def load_data(self):
        """Loads dataset for training."""
        self.X, self.y = load_iris(return_X_y=True)

    def train_model(self):
        """Trains the random forest model."""
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            random_state=self.random_state
        )
        self.model.fit(self.X, self.y)

    def save_model(self):
        """Saves the trained model to disk."""
        if self.model is None:
            raise ValueError("Model has not been trained yet.")
        joblib.dump(self.model, self.model_path)

    def run(self):
        """Executes the full training pipeline."""
        self.load_data()
        self.train_model()
        self.save_model()

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run()