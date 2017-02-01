//18/01/2017 Next iteration from SaveToSDandRTC
//24/01/2017 Now sends to computer GUI when USB connected, has external LED and buzzer

#include <Wire.h>
#include <GridEye.h>
#include <SD.h>
#include <SPI.h>
#include <RTCZero.h>

const int buzzerPin = 11;
GridEye myeye; //223Bytes
File myFile;
String filename="TEST0.CSV"; //seems to use caps no matter what
RTCZero rtc;

String val; // Data received from the serial port
int ledPin = 10; // Set the pin to digital I/O 12 (extra), 8 is the green inbuilt one
boolean ledState = LOW; //to toggle our LED
File file;

/* Change these values to set the current initial time */
const byte seconds = 0;
const byte minutes = 0;
const byte hours = 0;

/* Change these values to set the current initial date */
const byte day = 0;
const byte month = 0;
const byte year = 17;

void setup(void)
{
  rtc.begin(); // initialize RTC
  rtc.setTime(hours, minutes, seconds);
  rtc.setDate(day, month, year);
  Wire.begin();
  //Wire.setClock(400000L);
  myeye.setFramerate(1);// cause this is set to 1 second it means I'm sampling pretty fast

  Serial.begin(115200);
  
  pinMode(LED_BUILTIN, OUTPUT); //this is the red LED next to the microUSB on the feather board M0 datalogger
  pinMode(ledPin, OUTPUT); //this is the green LED
  pinMode(buzzerPin, OUTPUT); //pin 11, has the buzzer on it
   
  if (!SD.begin(4)) {
    Serial.println("initialization failed!");
    sadBeep();
    return;
  }
  //little bit of code to make it start a new file everytime it is turned on
  int fileNumber= 0;
  while(SD.exists(filename)){
    filename.replace(String(fileNumber), String(fileNumber+1));
    fileNumber++;
  }
  
}


int pixel[64]; 
uint8_t background[64] ={0}; 
int runs = 0; 
uint32_t stdDev; 
int32_t mean = 0; //this is only used in update Background but needs to be global for all pixels active case
uint8_t tempCache[64][5] ={0}; //saves last 5 temperature values for every pixel, using it like an array of queues 
uint8_t complen = 0; //component length
uint8_t occupiedCache[10] = {0}; //tracks occupied decisions
uint8_t occupiedCacheOldest=0;  //keeps track of the occupied cache's oldest value 


void loop(void)
{
  myeye.pixelOut(pixel); //read from grid eye
  
  int16_t temp;
    for ( int i = 0; i < 64; i++) {
      temp = pixel[i];
      if (temp > 0 && temp < 255) { //ensures value fits into uint_8 (1byte int) so is between 0 and 63.75°C
        addToTempCache(i, temp);
      }
    }
    
    
  if (runs < 10) { //update thermal background first few times
    updateBackground(pixel);
    dootdoot(); //this method makes a beep
  }
  else if(runs==10){//updates and beeps that it is done updating
    updateBackground(pixel);
    happyBeep();
  }
  else{
    occupied();
  }

  runs++;
  if(runs % 100 ==0){updateBackground(pixel);} //update every 100 runs
  //check if serial connected
  Serial.println("A"); //if the computer software is connected it picks this up
  if (Serial.available() > 0) { // If data is available to read,
    startGUI();
  } 
  delay(100);
}

// method to determine if the space is occupied or not
void occupied() {
  //get active pixels  
  int8_t active[64];
  uint8_t counter = 0; //keeps track of the length of active pixels
  int temp;
  uint8_t stdDev2 = 2 * stdDev; //an active pixel is one consistently hotter than 2 stdDevs above background
  for (uint8_t i = 0; i < 64; i++) {
    active[i] = -1; //clears out active each time, this is a sneaky work around
    if (tempCache[i][4] > background[i] + stdDev2 && searchCache(i, true)) {
      active[counter] = i;
      counter++;
    }
    //only 1 stdDev above background, searchCache has slightly different criteria
    else if( tempCache[i][4] > background[i] + stdDev && searchCache(i, false)) {
      active[counter] = i;
      counter++;
    }
  }
  //serialDisplay(active); //handy for debugging
  occupiedCache[occupiedCacheOldest]=connectedComponents(active, counter);
  occupiedCacheOldest++;
  if(occupiedCacheOldest > 9){ occupiedCacheOldest=0;}

  if (!saveToSD()) { occupiedDecision();} //saveToSD includes a call to occupiedDecision
}



//Wrapper method for the recursive method to find connected hot components
//passing length allows me to not have to search the whole 64 pixels for the normal case
uint8_t connectedComponents(int8_t active[], uint8_t len) {
 //Serial.println(); Serial.println("--  NEW CALL --"); Serial.println();

 uint8_t people= 0; //number of connected components
  for (uint8_t i = 0; i < len; i++) { 
    if (active[i] > -1) { //if there is an active pixel there, the recursive method deletes them as it finds them
      complen = 0;
      int total = con(active, i, len); //call the recursive method
      if (total > 4) {
        people++;
        
      }
    }
    
  }
  return people;
  
}


//returns number of pixels in a connected component
int con(int8_t active[], int start, int toEnd) {

  int cur = active[start];
  active[start] = -1; // delete from active
  start++;
  int total = 1;
  int index;

  //east
  if (cur / 8 == (cur + 1) / 8) {
    index = contains(active, start, toEnd, cur + 1);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }


  //south
  index = contains(active, start, toEnd, cur + 8);
  if (index != -1) {
    total += con(active, index, toEnd);
  }


  //west
  if (cur / 8 == (cur - 1) / 8) {
    index = contains(active, start, toEnd, cur - 1);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }


  //North
  index = contains(active, start, toEnd, cur - 8);
  if (index != -1) {
    total += con(active, index, toEnd);
  }
  
  //North East
  if (cur / 8 == (cur-7) /8) { //makes more sense to think cur+1-8
    index = contains(active, start, toEnd, cur - 7);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }
  
  //South East
  if (((cur+9) / 8) - (cur /8) ==1) { //Stops bad things happening when on the edge
    index = contains(active, start, toEnd, cur +9);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }
  
  //South West
  if (cur / 8 == (cur+7) /8) { 
    index = contains(active, start, toEnd, cur +7);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }
  
  //North West
  if ( (cur /8) - ((cur-9) / 8) ==1) { //Stops bad things happening when on the edge
    index = contains(active, start, toEnd, cur -9);
    if (index != -1) {
      total += con(active, index, toEnd);
    }
  }

  return total;
}

//averages the occupied cache to decide if occupied or not, prints and returns the result
String occupiedDecision(){
  uint8_t counter1=0; uint8_t counter2=0; //keep track of how many ones and twos are in occupiedCache
  for(int i =0; i<10; i++){
    if (occupiedCache[i]>1){counter2++;}
    else if (occupiedCache[i]>0){counter1++;}
  }
  String toReturn= "Not Occupied, ";
  //LED turns on when occupied
  if(counter2>4){ toReturn="Two People, "; digitalWrite(ledPin, HIGH);}
  else if ((counter2+ counter1) >4 ){ toReturn="One Person, "; digitalWrite(ledPin, HIGH);}
  else{ digitalWrite(ledPin, LOW);}
  //Serial.print(toReturn);
  return toReturn;
}

//returns the index of lookingFor in active[] or -1 if not found
int contains(int8_t active[], int start, int toEnd, int lookingFor) {
  for (int i = start; i < toEnd; i++) {
    if (active[i] == lookingFor && lookingFor != -1) {
      return i;
    }
  }
  return -1;
}

//Updates the thermal background and calculates standard deviation
void updateBackground(int data[64]) { //the active method
  digitalWrite(LED_BUILTIN, HIGH); //turn on LED 
  if (runs == 0) { //first time through 
    for ( int i = 0; i < 64; i++) {
      if (data[i] > 0 && data[i] < 255) {
        background[i] = data[i];
        
      }
      else {
        background[i] = 80; //fudge factor to avoid random memory values on noise corrupted backgrounds, makes it 20°C
      }
    }
  }
  else {
    
    //get active pixels  -copied from occupied method
    int8_t active[64];
    uint8_t counter = 0; //keeps track of the length of active pixels to calculate the mean later
    uint8_t stdDev2 = 2 * stdDev; //an active pixel is one consistently hotter than 2 stdDevs above background
    for (uint8_t i = 0; i < 64; i++) {
      active[i] = -1; //clears out active each time, this is a sneaky work around
      if (tempCache[i][4] > background[i] + stdDev2 && searchCache(i, true)) {
        active[counter] = i;
        counter++;
      }
      //only 1 stdDev above background, searchCache has slightly different criteria
      else if( tempCache[i][4] > background[i] + stdDev && searchCache(i, false)) {
        active[counter] = i;
        counter++;
      }
    } //end of code from occupied method
    
    if (active[49] > -1){//thermal overload- case where all but 15 pixels are active
      mean = mean+ stdDev2; //increase mean
      for (uint8_t i = 0; i < 64; i++) {
        background[i]=background[i] + stdDev2; //increase each individual background 
      }
      delay(10); digitalWrite(LED_BUILTIN, LOW); //LED is turned on while updating, so turn it off
      updateBackground(data); //recurse, increases performance
      return; //don't do the rest
    }
    
    //normal case
    mean = 0;
    counter=0; //now gonna use this same variable to count how many things we add to the background
      for (uint8_t i = 0; i < 64; i++) {
        if(! activeContains(active, i)){ //pixel is not active so same as before
          int32_t temp = (background[i] + tempCache[i][4]) / 2;
          if (temp > 0 && temp < 255) { //ensures value between 0 and 63.75°C and fits in a uint8_t
            background[i] = temp;
            mean += background[i];
            counter++;
          }
        }
      }
    
      //calculate standard deviation
    stdDev = 0;
    mean = mean / counter; //calculate mean
    for (uint8_t i = 0; i < 64; i++) {
      int16_t tem = background[i] - mean; // tem is temporary value
      tem = tem * tem; //square it

      stdDev += tem;
    }
    stdDev = stdDev / 64;
    stdDev = sqrt(stdDev);  

  }
  delay(10); digitalWrite(LED_BUILTIN, LOW);
}


void addToTempCache(int index, int toAdd){
  for (int i=0; i<5; i++){
    tempCache[index][i]= tempCache[index][i+1]; //shift everything along
  }
  tempCache[index][4]= toAdd;//add in the new value
}

//Search through tempCache to look for previous active pixels, stdDevs is true for 2 stdDevs and false for 1
boolean searchCache(int index, boolean stdDevs){ 
  int counter2StDev=0;  int counter1StDev=0;
  for(int i =0; i<4; i++){
    if(tempCache[index][i] > background[i] + 2*stdDev){counter2StDev++;}
    else if(tempCache[index][i] > background[i] + stdDev){counter1StDev++;}
  }
  //if the original reading was more than 2 std devs and another is above 2 std Devs or more than 3 are above 1 stdDev
  if((counter2StDev>0 || counter1StDev >2) && stdDevs){return true;} 
  
  //if the original was only one std Dev above the background
  else if(counter2StDev>1 || counter1StDev >2){return true;} 
  
  else{ return false;}

}

//does the list of active pixels contain this particular pixel (index)
boolean activeContains(int8_t active[], uint8_t index){
  for(uint8_t i =0; active[i] > -1 && i<64; i++){ //active becomes -1 after all useful values
      if(active[i]==index) return true;
  }
  return false;
}

//saves how many people and the time to the SD card, returns whether it was successful or not
boolean saveToSD(){
  if(myFile){myFile.close();} //closing it clears out the buffer, basically it ensures the last thing is written
  myFile = SD.open(filename, FILE_WRITE);
  if(myFile){
    myFile.print(occupiedDecision());
    myFile.println(returnTime());
    return true;
  }
  else{return false;}
}


//draws a little ascii picture over the serial monitor for debugging
void serialDisplay(int8_t active[]) {
  String toPrint= returnTime(); //doing one Serial.print makes the serial monitor faster and more readable
  toPrint+= '\n'; 
  
  //draws the ascii picture
  char disp[64];
  for ( uint8_t i = 0; i < 64; i++) {
    disp[i] = '*';
  }
  
  for (uint8_t i = 0; i < 64 ; i++) {
    if ( active[i] > 0 || (active[i] == 0 && i == 0)) {
      disp[active[i]] = 'o';
      //Serial.print(active[i]); Serial.print(", ");
    }
  }
  

  for ( uint8_t i = 0; i < 8; i++) {
    for(uint8_t j=0; j<8; j++){
      toPrint += disp[(i*8)+j];
      toPrint += ' ';
    }
    toPrint +='\n';
  }
 Serial.println(toPrint);
}

String returnTime(){
  String date= "";
  date+=rtc.getHours();
  date+=":";
  date+=rtc.getMinutes();
  date+=":";
  date+=rtc.getSeconds();
  date+=" ";
  date+=rtc.getDay();
  date+=":";
  date+=rtc.getMonth();
  date+=":";
  date+=rtc.getYear();
  date+= " ";
  return date;
}

void startGUI(){
  val = Serial.readString(); // read it and store it in val

    if(val == "list"){
      file = SD.open("/");
      file.rewindDirectory();
      printDirectory(file, 0);
      Serial.println();
      Serial.print("end\n");
      Serial.println(); 
    }
    else if(val.startsWith("fname ")){
      val.remove(0, 6);
      Serial.print("filename: "); Serial.println(val);
      writeFileToSerial(val);
    }

    else if (val.startsWith("delete ")){
      val.remove(0, 7);
      SD.remove(val);
      Serial.print("removed\n");
      Serial.println();
    }
}


void writeFileToSerial(String filename){
  file = SD.open(filename);

  // if the file is available, write to it:
  if (file) {
    char buf[32];
    memset(buf,'\0', sizeof(buf));
    while (file.available()) {
      file.read(buf, 31);
      Serial.write(buf);
      memset(buf,'\0', sizeof(buf));
      ledState = !ledState; //flip the ledState
      digitalWrite(ledPin, ledState); 
      
    }
    file.close();
    digitalWrite(ledPin, LOW);
    Serial.println(); Serial.print("end\n"); Serial.println();
  }
  // if the file isn't open, pop up an error:
  else {
    Serial.print("error opening file");
  }

}

//retreived from https://www.arduino.cc/en/Tutorial/listfiles
void printDirectory(File dir, int numTabs) {
  while (true) {

    File entry =  dir.openNextFile();
    if (! entry) {
      // no more files
      
      break;
    }
    for (uint8_t i = 0; i < numTabs; i++) {
      Serial.print('\t');
    }
    Serial.print(entry.name());
    if (entry.isDirectory()) {
      Serial.println("/");
      printDirectory(entry, numTabs + 1);
    } else {
      // files have sizes, directories do not
      Serial.print("\t\t");
      Serial.println(entry.size(), DEC);
    }
    entry.close();
  }
}

void sadBeep(){
  tone(buzzerPin, 700, 300);
  delay(1000);
  for( int f=500; f>400; f=f-5){
    tone(buzzerPin, f, 100);
    delay(50);
  }
}

void dootdoot(){
  tone(buzzerPin, 523, 100);
  delay(100);
  tone(buzzerPin, 659, 100);
  delay(500);
}

void happyBeep(){
  tone(buzzerPin, 523, 200);
  delay(200);
  tone(buzzerPin, 659, 200);
  delay(200);
  tone(buzzerPin, 786, 200);
  delay(200);
  tone(buzzerPin, 1026, 800);
  delay(500);
  tone(buzzerPin, 523, 500);
}

//handy little method for finding how much ram is free, useful for debugging sometimes
/*int freeRam () {
  extern int __heap_start, *__brkval; 
  int v; 
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval); 
}*/
