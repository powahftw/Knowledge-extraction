#from tqdm import tqdm
import string
import difflib
import wikidata
from wikidata import client, entity
import requests
import json

class RelationshipExtractor:

    def __init__(self):
        self.cache = {}
        self.client = client.Client()  # doctest: +SKIP
        self.mode = 1 # 1 for searching the propriety with values, 0 for searching the values throught the propriety
        self.VERBOSE = False
        
    def set_mode(self, m):
        """
        Set the current operating mode of the RelationshipExtractor
        Args:
            m (int):  1 for searching the propriety with values, 0 for searching the values throught the propriety
        """
        if m in (0, 1): self.mode = m
            
    class NoRelevantResult(Exception):    pass
    
    def search_id(self, keyword):
        """
        Query keyword using wikidata API to retrieve it's ID
        Args:
            keyword (string): Item to search on wikidata.
        Returns:
            idd (string): Wikidata ID of the searched item.
        """
        if not keyword: raise ValueError

        BASE_URL = "https://www.wikidata.org/w/api.php?action=wbsearchentities&search={}&language=en&format=json"

        resp = requests.get(url=BASE_URL.format(keyword))
        json_resp = json.loads(resp.text)

        if not len(json_resp['search']): 
            print("No relevant page found")        
            raise NoRelevantResult

        idd = json_resp['search'][0]['id'] 
        print("\n\n--\n\n")
        print("ID of Item to retrieve\t" + idd)
        print("\n\n--\n\n")
        return idd

    def visualize_prop(self, d):
        """
        Args:
            d (dict): Dictionary of Prop -> Values to visualize.
        """
        class SetEncoder(json.JSONEncoder): # Custom encoder to handle json-dumping set
            def default(self, obj):
                if isinstance(obj, set):
                    return list(obj)
                return json.JSONEncoder.default(self, obj)
        print("\n\n--\n\n")
        print (json.dumps(d, sort_keys=True, indent=4, cls=SetEncoder))
        print("\n\n--\n\n")
        
    def get_propvalues(self, idd):
        """
        Retrieve and store the Wikidata information about an Entity.
        Args:
            idd (string): Wikidata ID of the item.
        Returns:
            prop_d (dict): Dictionary Prop -> Values of certain Wikidata Item.
        """
        if not idd: raise ValueError

        if idd in self.cache: return self.cache[idd]
        entity = self.client.get(idd, load = False)

        prop_d = {}

        n = len(list(entity))
        for idx, x in enumerate(list(entity)): # Iterate over properties

            prop = self.client.get(x.id, load = True)
            print("\n{}/{} Propriety ID:\t {} \tPropriety NAME:\t {}".format(idx+1, n, str(x.id), str(prop.label))) 

            prop_d[str(prop.label).lower()] = set() # Set of values for each proprieties 

            try:
                for p in entity.getlist(prop):
                    if type(p) is wikidata.entity.Entity: # Propriety is a wikidata entity
                        print(p.label)
                        prop_d[str(prop.label).lower()].add(str(p.label)) # Skip duplicate
                    else: 
                        print(p) # Propriety is a value
                        prop_d[str(prop.label).lower()].add(str(p))
            except Exception as e: # Handling  of unsupported DataValue
                try:
                    param = str(e).split("unsupported type: ")[1].replace("'",'"') # Value type
                    d = json.loads(param)
                    print(d["value"]["amount"])
                    prop_d[str(prop.label).lower()].add(str(d["value"]["amount"]))
                except:
                    print ("Unhandled type (GPS, ...)")
                    print () # Other unhandled type

        self.cache[idd] = prop_d
        return prop_d

    def find_similarities(self, prop_d, to_find):
        """
        Args:
            prop_d (dict): Dictionary Prop -> Values of certain Wikidata Item.
            to_find (string): Element to search for the connection with the Item.
        Returns:
            results (List): List of propriety which make a match between the prop_d and to_find .
        """
        results = []

        if self.mode: print("\n-Normal MODE-\n")
        elif not self.mode: print("\n-Reverse MODE-\n")

        for prop_name, value in prop_d.items():
            for value_name in value:
                if self.mode and RelationshipExtractor.comparison_strategy(to_find, value_name):
                    results.append(prop_name)         
                elif not self.mode and RelationshipExtractor.comparison_strategy(to_find, prop_name):
                    results.append(value_name)
        for result in results:
            print("{} | Possible match: {}".format(to_find, result))
        return results

    def comparison_strategy(s1, s2):
        """
        Args:
            s1 (string): First string to compare.
            s2 (string): Second string to compare.
        Returns:
            Bool (Bool): Boolean check if s1 and s2 are deemed enought similar.
        """                    
        return (difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()) > 0.9                  

    def extract(self, to_search, relation_with):
        print("PROCESSING {}".format(to_search))
        idd = self.search_id(to_search) # Retrieve the wikidata ID for the best possible result.
        prop_d = self.get_propvalues(idd)
        if self.VERBOSE:
            self.visualize_prop(prop_d)
        self.find_similarities(prop_d, relation_with)
        

re = RelationshipExtractor()

re.extract("Julius Caesar", "politician")
