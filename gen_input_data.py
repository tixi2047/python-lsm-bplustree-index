import random

names_male = ['John', 'Mike', 'David', 'Paul', 'Steve', 'Mark', 'James', 'Chris', 'Kevin', 'Brian', 'Tom', 'Alex', 'Eric', 'Ryan']
names_female = ['Anna', 'Lisa', 'Sarah', 'Emma', 'Kate', 'Mary', 'Jane', 'Lucy', 'Rose', 'Tina', 'Amy', 'Lily', 'Mia', 'Nina']
jobs = ['Driver', 'Chef', 'Nurse', 'Agent', 'Clerk', 'Baker', 'Writer', 'Singer', 'Dancer', 'Farmer']
genders = ['M', 'F']


with open('input_data.txt', 'w') as file:

    for i in range(1, 4501):
        gender = random.choice(genders)
        
        if gender == 'M':
            name = random.choice(names_male)
        else:
            name = random.choice(names_female)
        
        job = random.choice(jobs)
        experience = random.randint(1, 45)
        income = random.randint(1, 120)
        
        file.write(f"{i},{name},{gender},{job},{income},{experience}\n")

print("\nFile 'input_data.txt' is created successfully!")