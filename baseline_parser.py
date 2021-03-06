import math
import mysql.connector
import re
from copy import deepcopy
from sets import Set
import pickle
import inflect
import spacy
import unicodedata

nlp = spacy.load('en')

p = inflect.engine()

config = {
  'user': 'root',
  'password': 'root',
  'host': 'localhost',
  'database': 'mysql',
  'raise_on_warnings': True,
}

mismatchList = []; 

link = mysql.connector.connect(**config)
cursor = link.cursor()
cookingDescriptions = {'cut', 'small', 'medium', 'sliced', 'large', 'very', 'more', 'squeezed', 'freshly', 'chopped', 'peeled', 'cored', 'ground', 'finely'}
cookingMeasurements = {'pinch', 'dash', 'by', 'of', 'into', 'or', 'for', 'to', 'can', 'jar', 'and', 'with', 'teaspoon', 'teaspoons', 'tsp', 'tsp.', 'tablespoon', 'tablespoons', 'tbsp', 'tbsp.', 'cup', 'cups', 'ounce', 'ounces', 'oz', 'oz.', 'gram', 'grams'}
compoundIngredientDict = pickle.load( open( "save_compound_ingredients.p", "rb" ) )
ingredientSet = Set(pickle.load( open( "save_ingredient_list.p", "rb" ) ) )
cookingVerbSet = Set(pickle.load( open( "save_cooking_verb.p", "rb" ) ) )
#groundTruth = pickle.load( open( "ground_truth.p", "rb" ) ) 
groundTruth = pickle.load( open( "ground_truth_cookie.p", "rb" ) ) 
hesitateVerbs = pickle.load( open( "save_hesitate_verbs.p", "rb" ) ) 
cookingVerbDict = dict.fromkeys(cookingVerbSet, 0)

print "Opening the file..."
#target = open('output-cookie.txt', 'w')
#target.truncate()

def extractIngredientKeysPruning(ingredient):
	ingredientsCopy = deepcopy(ingredient)
	for x in range(len(ingredient)):
		wordChunk = ingredient[x]
		if len(wordChunk) > 0:
			if re.search('\d+(.\d+)?', wordChunk):
				ingredientsCopy.remove(wordChunk)
			elif re.search('\(|\)', wordChunk):
				ingredientsCopy.remove(wordChunk)
			elif wordChunk in cookingMeasurements:
				ingredientsCopy.remove(wordChunk)
			elif wordChunk in cookingDescriptions:
				ingredientsCopy.remove(wordChunk)
	return ingredientsCopy

def cleanRawString(wordChunk, verbFlag):
	wordChunk = wordChunk.replace("'", "")
	wordChunk = wordChunk.replace(",", "")
	wordChunk = wordChunk.replace("[", "")
	wordChunk = wordChunk.replace("]", "")
	wordChunk = wordChunk.replace('"', '')
	wordChunk = wordChunk.replace('(', '')
	wordChunk = wordChunk.replace(')', '')	
	wordChunk = wordChunk.strip()
	wordChunk = wordChunk.lower()
	if not verbFlag and p.singular_noun(wordChunk):
		wordChunk = p.singular_noun(wordChunk)
	return wordChunk

def extractIngredientKeys(ingredient):
	flag = True
	ingredient = [str(x) for x in ingredient]
	compoundKeys = Set([])
#	ingredient = [cleanRawString(x, None) for x in ingredient]
	for x in range(len(ingredient)):
		ingredient[x] = cleanRawString(ingredient[x], None)
		elem = ingredient[x]
		if elem in compoundIngredientDict:
			extraKeys = compoundIngredientDict[elem]
			print Set(ingredient)
			print Set(extraKeys)
			intersection = Set(extraKeys) & Set(ingredient)
			if intersection:
				compoundKeys = intersection
				compoundKeys.add(elem)
				flag = False
				break

	#		elif 'isolated' not in compoundIngredientDict[elem]: 
	#		else:
	#			compoundKeys.add(elem)
	#			flag = False
	#			break
	if (flag):
		for y in range(len(ingredient)): 
			if ingredient[y] in ingredientSet:
				compoundKeys.add(ingredient[y])
	#	elif elem in ingredientSet:
	#		compoundKeys.add(elem)
	#		flag = False
	#		break
	if len(compoundKeys) is 0:
	#	return Set(extractIngredientKeysPruning(ingredient) )
		return Set([])
	else:
		return compoundKeys

def extractInstructionKeys(instruction):
	splitInstruction = [cleanRawString(str(x.encode('ascii','ignore')), True) for x in instruction.split()]
	return splitInstruction

def extractInstructionLabel(instruction, labels):
	flag = True
	backup = []
	assured = []
	for x in range(len(instruction)):
		wordChunk = instruction[x]
		if wordChunk.upper() in cookingVerbSet:
			if x is 0 or wordChunk in labels or wordChunk.upper() not in hesitateVerbs:
				cookingVerbDict[wordChunk.upper()] += 1
				assured.append(wordChunk)
			else:
				backup.append(wordChunk)
	if len(assured) > 0:
		return assured
	elif len(backup) > 0:
		return backup
	else:
		return list(labels)

def print_fine_pos(token):
    return (token.tag_)

#rewrite canUseSingle so that you take the greatest instead
def canUseSingle(wordChunk, ingrSet):
	currWord = ''.join(list(wordChunk & ingrSet) )
	otherWord = ''.join(list(ingrSet - wordChunk) )
	if currWord in compoundIngredientDict:
		moreKeys = compoundIngredientDict[currWord]
		if otherWord not in moreKeys: 
			return False
		if moreKeys[otherWord] is None:
			return True
		if moreKeys[otherWord] is 1 or 2:
			return False
	elif otherWord in compoundIngredientDict:
		moreKeys = compoundIngredientDict[otherWord]
		if currWord not in moreKeys: 
			return False
		if moreKeys[currWord] is None:
			return False
		if moreKeys[currWord] is 1:
			return True
	return False



def pos_tags(sentence):
	tokens = nlp(sentence)
	tags = []
	for tok in tokens:
		print (tok ,str(print_fine_pos(tok)) )
		if 'V' in str(print_fine_pos(tok)):
			tags.append(cleanRawString(str(tok), None))
	return Set(tags)

#set of tuples of used ingredients + the new ingredient

#query = ("SELECT name, type, ingredients, recipe_instructions FROM cooking_recipes_reformat WHERE type='sandwich'")
query = 'SELECT name, type, ingredients, recipe_instructions FROM cooking_recipes_reformat WHERE type="cookie" AND name LIKE "%chocolate chip%"'; 
cursor.execute(query)
results = cursor.fetchall()
finalAssociationsCounter = 0
matches = 0

for name, type, rawIngr, rawInstr in results:
	ingredients = []
	instructions = []

#	INSERT INTO TABLE: recipe
	# query = ("INSERT INTO recipes(recipe_name, type) VALUES(%s, %s)")
	# cursor.execute(query, (name, type))
	# link.commit()
	# query = ("SELECT LAST_INSERT_ID()")
	# cursor.execute(query)
	# recipe_id = cursor.fetchone()[0]

	#pre-processing so that each block-text is split accordingly

	ingrArr = rawIngr.split(', u')
	
	for x in ingrArr:
		#INSERT INTO TABLE: ingredients
		print x
		ingredient = extractIngredientKeys(x.split())
		# query = ("INSERT INTO ingredients(recipe_id, text_name, raw_text) VALUES(%s, %s, %s)")
		# cursor.execute(query, (recipe_id, ' '.join(ingredient), x))
		# link.commit()
		ingredients.append(extractIngredientKeys(x.split()))
	lineInstructions = rawInstr.split('.')

	#For each line of instructions
	for instruction in lineInstructions:
		print instruction
		labels = pos_tags(instruction)
		instruction = unicodedata.normalize('NFKD', instruction).encode('ascii','ignore')
	#	target.write(instruction + "\n")
	#	INSERT INTO TABLE: steps
		# query = ("INSERT INTO steps(recipe_id, text_line) VALUES(%s, %s)")
		# cursor.execute(query, (recipe_id, instruction))
		# link.commit()
		# query = ("SELECT LAST_INSERT_ID()")
		# cursor.execute(query)
		# step_id = cursor.fetchone()[0]

		instructionKeys = extractInstructionKeys(instruction)
		print instructionKeys
		finalLabel = extractInstructionLabel(instructionKeys, labels)
	#	target.write("Ingredients: " + str(ingredients) + "\n")
		compoundFlag = False
		
	#	target.write(str(finalLabel) + "\n")
		usedIngredients = [0] * len(ingredients)
		finalAssociations = {}
	 	currIndex = 0
	 	rank = 0
	 	currAction ='#no-action#'
	 	finalAssociations[currAction] = []
	 	for x in range(len(instructionKeys)):
	 		wordChunk = instructionKeys[x]
	 		associatedIngredient = []

	 		if compoundFlag:
	 			compoundFlag = False
	 			continue
	 		if currIndex < len(finalLabel) and wordChunk is finalLabel[currIndex]:
	 			currIndex += 1
	 		#  	query = ("INSERT INTO node(recipe_id, step_id, class, rank, text) VALUES(%s, %s, %s, %s, %s)")
				# cursor.execute(query, (recipe_id, step_id, 'action', rank, wordChunk))
				# link.commit()
				rank += 1
				if wordChunk in finalAssociations:
					wordChunk = wordChunk + "2"
	 			finalAssociations[wordChunk] = []
	 			currAction = wordChunk
	 		for y in range(len(ingredients)):
	 			if p.singular_noun(wordChunk):
					wordChunk = p.singular_noun(wordChunk)
	 			ingredient = ingredients[y]
	 			ingrSet = Set(ingredient)
	 			if wordChunk in ingrSet and not usedIngredients[y]:
	 				if len(ingrSet) > 1:
	 					if (x < len(instructionKeys)-1 and instructionKeys[x+1] in ingrSet):
	 						associatedIngredient.append(wordChunk)
	 						associatedIngredient.append(instructionKeys[x+1]) 
	 						compoundFlag = True
	 					elif (x > 0 and instructionKeys[x-1] in ingrSet):
	 						associatedIngredient.append(wordChunk)
	 						associatedIngredient.append(instructionKeys[x-1]) 
	 						compoundFlag = True
	 					elif canUseSingle(Set([wordChunk]), ingrSet):
	 						associatedIngredient.append(wordChunk)
	 				else:
	 					associatedIngredient.append(wordChunk)
	 				usedIngredients[y] = 1
	 				break

	 		if (len(associatedIngredient) > 0):
	 		#  	print "Associated Ingredients: " + str(associatedIngredient)
	 		#  	query = ("INSERT INTO node(recipe_id, step_id, class, rank, text) VALUES(%s, %s, %s, %s, %s)")
				# cursor.execute(query, (recipe_id, step_id, 'ingredient', rank, ' '.join(associatedIngredient)))
				# link.commit()
				rank += 1
				finalAssociations[currAction].append(associatedIngredient)
	 		#	target.write("Associated Ingredients: " + str(associatedIngredient) + "\n")
	 	print ingredients
	 	print "Final Associations: ", finalAssociations
	 	# if finalAssociationsCounter >= len(groundTruth):
	 	#  	print float(matches)/finalAssociationsCounter
	 	#  	print cookingVerbDict
	 	#  	print mismatchList
	 	# 	#return
	 #   	print groundTruth[finalAssociationsCounter]
		# if Set(groundTruth[finalAssociationsCounter]) == Set(finalAssociations):
	 #   		print "match"
	 #   		matches += 1
	 #   	else:
	 #   		print "mismatch"
		#   	mismatchList.append(finalAssociationsCounter)
	 #  	print finalAssociationsCounter
	  	finalAssociationsCounter += 1
	 	#target.write("Final Associations: " + str(finalAssociations) + "\n")
		print "#####################################"

		#target.write("####################################" + "\n")
target.close()

