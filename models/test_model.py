from models.health_model import train_model

model = train_model()

print(model.predict_proba([[30,80,200]]))
print(model.predict_proba([[55,150,260]]))