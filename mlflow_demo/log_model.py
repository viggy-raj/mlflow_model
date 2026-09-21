import mlflow as mlf
import joblib

class MLflowModelLogger:
    """Class to handle loading a model and registering it with MLflow."""
    
    def __init__(self, tracking_uri="http://127.0.0.1:5000", model_path="model.pkl", model_name="simple classifier"):
        self.tracking_uri = tracking_uri
        self.model_path = model_path
        self.model_name = model_name
        self.model = None

    def setup(self):
        """Configures MLflow tracking URI."""
        mlf.set_tracking_uri(self.tracking_uri)

    def load_model(self):
        """Loads the pre-trained model from disk."""
        self.model = joblib.load(self.model_path)

    def log_and_register(self):
        """Logs the model to MLflow and registers it in the Model Registry."""
        with mlf.start_run() as run:
            # model logging
            mlf.sklearn.log_model(self.model, self.model_name)
            # gets the run id of the current run
            run_id = run.info.run_id
            
            # model registration logic
            result = mlf.register_model(
                model_uri=f"runs:/{run_id}/{self.model_name}",
                name=self.model_name
            )
            return result

    def run(self):
        """Executes the full logging and registration pipeline."""
        self.setup()
        self.load_model()
        return self.log_and_register()

if __name__ == "__main__":
    logger = MLflowModelLogger()
    logger.run()
